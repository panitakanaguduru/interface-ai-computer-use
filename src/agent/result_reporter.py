def build_final_result(
    task,
    answer,
    observation,
    history,
):

    return {
        "task": task,
        "status": "completed",
        "answer": answer,
        "final_url": observation.get("url"),
        "page_title": observation.get("title"),
        "actions_executed": len(history),
    }


def print_final_result(result):

    print(
        "\n========== FINAL RESULT =========="
    )

    print("Task:", result["task"])
    print("Status:", result["status"])

    print("\nAnswer:")
    print(result["answer"])

    print(
        "\nFinal URL:",
        result["final_url"],
    )

    print(
        "Page:",
        result["page_title"],
    )

    print(
        "Browser actions executed:",
        result["actions_executed"],
    )

    print(
        "=================================="
    )