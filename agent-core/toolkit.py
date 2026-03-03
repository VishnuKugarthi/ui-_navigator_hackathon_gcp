from typing import Dict, Any, Callable

class UIToolkit:
    """Shared UI Automation Toolkit Abstractions"""
    
    @staticmethod
    def describe_page(screenshot: str) -> str:
        # Stub: send to vision model to get natural language description
        return "Page contains tables, buttons, cards"

    @staticmethod
    def locate_element(query: str, screenshot: str) -> Dict[str, int]:
        # Stub: returns coordinates
        return {"x": 100, "y": 200, "width": 50, "height": 20}

    @staticmethod
    def click_element(element_type: str, label: str, confidence: float) -> bool:
        print(f"Clicking {element_type} with label: {label}")
        return True

    @staticmethod
    def extract_table(region: Dict[str, int], screenshot: str) -> str:
        # Stub: returning CSV string
        return "Month,Revenue\nJan,10000\nFeb,15000\nMar,20000"

    @staticmethod
    def type_text(location: Dict[str, int], text: str) -> bool:
        print(f"Typing '{text}' at {location}")
        return True

    @staticmethod
    def select_range(range_obj: str) -> bool:
        print(f"Selecting range {range_obj}")
        return True

    @staticmethod
    def switch_tab(tab_title: str) -> bool:
        print(f"Switching to tab containing '{tab_title}'")
        return True

    @staticmethod
    def scroll(direction: str, delta: int) -> bool:
        print(f"Scrolling {direction} by {delta}")
        return True

tools_map: Dict[str, Callable] = {
    "describe_page": UIToolkit.describe_page,
    "locate_element": UIToolkit.locate_element,
    "click_element": UIToolkit.click_element,
    "extract_table": UIToolkit.extract_table,
    "type_text": UIToolkit.type_text,
    "select_range": UIToolkit.select_range,
    "switch_tab": UIToolkit.switch_tab,
    "scroll": UIToolkit.scroll,
}
