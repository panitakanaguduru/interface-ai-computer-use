from playwright.sync_api import Page


def observe_page(page: Page):
    """
    Observe the current browser page.

    Returns information that the LLM can use
    to decide the next action.
    """

    observation = {
        "url": page.url,
        "title": page.title(),
        "inputs": [],
        "buttons": [],
        "text": page.locator("body").inner_text(),
    }

    # -----------------------------------
    # INPUTS
    # -----------------------------------

    inputs = page.locator("input")

    for i in range(inputs.count()):

        element = inputs.nth(i)

        observation["inputs"].append({
            "id": element.get_attribute("id"),
            "name": element.get_attribute("name"),
            "type": element.get_attribute("type"),
            "placeholder": element.get_attribute("placeholder"),
            "value": element.input_value(),
        })

    # -----------------------------------
    # BUTTONS
    # -----------------------------------

    buttons = page.locator("button")

    for i in range(buttons.count()):

        element = buttons.nth(i)

        observation["buttons"].append({
            "id": element.get_attribute("id"),
            "text": element.inner_text(),
        })

    return observation