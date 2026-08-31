from .agent import agent_chat_impl


def agent_chat_l2(
    prompt: str
) -> str:

    return agent_chat_impl(
        prompt
    )
