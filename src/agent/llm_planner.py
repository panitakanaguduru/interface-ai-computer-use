import json
import os

from openai import OpenAI


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def llm_plan(task, observation):
    """
    Ask the LLM to choose the next browser action.

    Supported actions:
        fill
        click
        done
    """

    prompt = f"""
You are controlling a browser to complete a user task.

USER TASK:
{task}

CURRENT PAGE OBSERVATION:
{json.dumps(observation, indent=2)}

You must choose exactly ONE next action.

Available actions:

1. Fill an input:
{{
    "action": "fill",
    "selector": "#element-id",
    "value": "text"
}}

2. Click a button:
{{
    "action": "click",
    "selector": "#element-id"
}}

3. Finish the task:
{{
    "action": "done",
    "message": "actual answer to the user's task"
}}

IMPORTANT RULES:

- Return ONLY valid JSON.
- Do not return markdown.
- Do not explain your reasoning.
- Use only elements that exist in the observation.
- Never invent member information.
- Never invent account, transaction, or claim information.
- Base answers only on CURRENT PAGE OBSERVATION.
- If the task asks for a member, first search for that member.
- If the requested member information is not yet visible,
  do NOT return done.
- Once the required information is visible, analyze it and
  answer the user's exact question.
- For calculations or comparisons, use the values visible
  in the page observation.
- If asked for the largest transaction, compare all visible
  transaction amounts.
- If asked for the latest claim, compare claim dates.
- If asked for transactions over an amount, identify every
  visible transaction satisfying that condition.
- If asked for total account balance, add all visible account
  balances.
- If asked how many claims have a particular status, count
  all visible matching claims.
- When returning done, the message must contain the useful
  answer, not merely "Task completed successfully."
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
    )

    raw_response = response.output_text.strip()

    print("\n--- LLM RAW RESPONSE ---")
    print(raw_response)
    print("------------------------")

    # Remove accidental Markdown fences if the model
    # ever returns them.
    if raw_response.startswith("```"):
        raw_response = raw_response.replace(
            "```json",
            "",
            1,
        )

        raw_response = raw_response.replace(
            "```",
            "",
        )

        raw_response = raw_response.strip()

    try:
        action = json.loads(raw_response)

    except json.JSONDecodeError as error:
        raise ValueError(
            "LLM returned invalid JSON: "
            f"{raw_response}"
        ) from error

    return action