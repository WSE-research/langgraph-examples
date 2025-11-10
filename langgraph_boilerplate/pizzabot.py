from typing import TypedDict

from langgraph.graph import END, StateGraph
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
)
from enum import Enum
import requests
from typing import Dict, List, Any, Optional


class ChatbotState(TypedDict):
    """
    Messages have the type "list". The `add_messages` function
    in the annotation defines how this state key should be updated
    (in this case, it appends messages to the list, rather than overwriting them)
    """
    input: str
    slots: dict
    messages: list
    active_order: bool
    ended: bool

class Nodes(Enum):
    ENTRY = "entry"
    CHECKER = "checker"
    ORDER_FORM = "order_form"
    RETRIEVAL = "retrieval"
    END = "end"

class OrderSlots(Enum):
    PIZZA_NAME = "pizza_name"
    CUSTOMER_ADDRESS = "customer_address"

class CheckerNode:
    """
    This node checks whether user input is valid
    """
    
    def __init__(self, keywords=None):
        if keywords is None:
            keywords = ["order", "pizza"]
        self.keywords = keywords

    def invoke(self, state: ChatbotState) -> dict[str, list | dict | bool]:
        """
        Checks whether the input is a valid request for pizza order
        """
        if state['active_order']:
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "active_order": state["active_order"],
                "ended": state["ended"]
            }
        
        _input = state['input'].lower()
        if not all(keyword in _input for keyword in self.keywords):
            state['messages'].append(AIMessage(content="Invalid order. Please specify a pizza order. Try writing 'I want to order a pizza'."))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "active_order": state["active_order"],
                "ended": state["ended"]
            }
        else:
            state['active_order'] = True
            # state['messages'].append(AIMessage(content="Your pizza order is valid."))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "active_order": state["active_order"],
                "ended": state["ended"]
            }
        
    
    def route(self, state: ChatbotState) -> str:
        """
        Routes to the next node
        """
        if state['active_order']:
            return Nodes.RETRIEVAL.value
        else:
            return END

class OrderNode:
    """
    Collects the slots for the pizza order
    """
    
    def __init__(self):
        pass

    def invoke(self, state: ChatbotState) -> dict[str, list | dict | bool] | None:
        """
        Returns fallback message
        """

        required_slots = [OrderSlots.PIZZA_NAME, OrderSlots.CUSTOMER_ADDRESS]
        missing_slots = [slot.value for slot in required_slots if slot.value not in state['slots'].keys()]

        if not missing_slots:
            state['messages'].append(AIMessage("Thank you for providing all the details. Your order is being processed!"))
            state['ended'] = True
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }

        next_slot = missing_slots[0]
        if next_slot == OrderSlots.PIZZA_NAME.value:
            state['messages'].append(AIMessage("What pizza would you like to order?"))
            state["messages"].append(FunctionMessage(content=OrderSlots.PIZZA_NAME, name=OrderSlots.PIZZA_NAME.value))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }

        elif next_slot == OrderSlots.CUSTOMER_ADDRESS.value:
            state['messages'].append(AIMessage("What is your delivery address?"))
            state["messages"].append(FunctionMessage(content=OrderSlots.CUSTOMER_ADDRESS, name=OrderSlots.CUSTOMER_ADDRESS.value))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        return None
    
class RetrievalNode:
    """
    This node extracts the information from user input
    """
    
    def __init__(self):
        pass

    def invoke(self, state: ChatbotState) -> dict[str, list | dict | bool] | None:
        """
        Extracts the information from user input
        """
        last_message = state["messages"][-1] if len(state["messages"]) > 0 else "No message"

        if not state['active_order'] or not isinstance(last_message, FunctionMessage):
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        
        _input = state['input'].lower()

        if last_message.content == OrderSlots.PIZZA_NAME.value:
            # available_pizzas = api_client.list_pizzas()
            # pizza_names = [pizza['name'].lower() for pizza in available_pizzas]
            #
            # print("input: " + _input)
            # print("is in pizza_names: " + str(_input in pizza_names))
            #
            # if _input not in pizza_names:
            #     state['messages'].append(AIMessage(content="Sorry, that pizza is not available. Please choose from our menu."))
            #     return {
            #         "messages": state["messages"],
            #         "slots": state["slots"],
            #         "ended": state["ended"]
            #     }

            state['slots'][OrderSlots.PIZZA_NAME.value] = _input
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        elif last_message.content == OrderSlots.CUSTOMER_ADDRESS.value:
            state['slots'][OrderSlots.CUSTOMER_ADDRESS.value] = _input
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        return None

class PizzaAPIClient:
    # Communicates with https://demos.swe.htwk-leipzig.de/pizza-api/docs
    def __init__(self, base_url: str = "https://demos.swe.htwk-leipzig.de/pizza-api"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'accept': 'application/json',
            'Content-Type': 'application/json'
        })

    #   GET /pizza - List available pizzas
    def list_pizzas(self) -> List[Dict[str, Any]]:
        try:
            response = self.session.get(f"{self.base_url}/pizza")
            response.raise_for_status()
            print(response.json())
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching pizzas: {e}")
            return []

    #     POST /address/validate - Validate delivery address
    def validate_address(self, address: str) -> Dict[str, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/address/validate",
                json = {"address": address}
            )
            response.raise_for_status()
            print(response.json())
            return response.json()
        except requests.RequestException as e:
            print(f"Error validating address: {e}")
            return {"valid": False, "error": str(e)}

    #     POST /order - Create a new pizza order
    def create_order(self, pizza_name: str, address: str) -> Dict[str, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/order",
                json = {
                    "pizza_name": pizza_name,
                    "delivery_address": address
                }
            )
            response.raise_for_status()
            print(response.json())
            return response.json()
        except requests.RequestException as e:
            print(f"Error creating order: {e}")
            return {"success": False, "error": str(e)}

    #     GET /order/{order_id} - Get order status
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        try:
            response = self.session.get(f"{self.base_url}/order/{order_id}")
            response.raise_for_status()
            print(response.json())
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching order status: {e}")
            return {"status": "unknown", "error": str(e)}


if __name__ == "__main__":
    # Initialize nodes
    order_node = OrderNode()
    checker_node = CheckerNode()
    retrieval_node = RetrievalNode()
    api_client = PizzaAPIClient()

    workflow = StateGraph(ChatbotState)
    workflow.add_node(Nodes.CHECKER.value, checker_node.invoke)
    workflow.add_node(Nodes.RETRIEVAL.value, retrieval_node.invoke)
    workflow.add_node(Nodes.ORDER_FORM.value, order_node.invoke)

    workflow.add_conditional_edges(
        Nodes.CHECKER.value,
        checker_node.route,
        {
            Nodes.RETRIEVAL.value: Nodes.RETRIEVAL.value,
            END: END,
        }
    )
    workflow.add_edge(Nodes.RETRIEVAL.value, Nodes.ORDER_FORM.value)
    workflow.add_edge(Nodes.ORDER_FORM.value, END)
    
    workflow.set_entry_point(Nodes.CHECKER.value)
    graph = workflow.compile()

    # START DIALOGUE: first message
    print("-- Chatbot: ", "Hi! I am a pizza bot. I can help you order a pizza. What would you like to order?")
    user_input = input("-> Your response: ")
    outputs = graph.invoke({"input": user_input, "slots": {}, "messages": [], "active_order": False, "ended": False})

    while True:
        print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
        user_input = input("-> Your response: ")

        outputs = graph.invoke({"input": user_input, "slots": outputs["slots"], "messages": outputs["messages"], "active_order": outputs["active_order"], "ended": outputs["ended"]})

        # check if the conversation has ended
        if outputs["ended"]:
            print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
            break