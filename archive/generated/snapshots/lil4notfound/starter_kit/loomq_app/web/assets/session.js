export class ConversationSession {
  constructor(maxMessages = 4) {
    this.maxMessages = maxMessages;
    this.messages = [];
  }

  historyForRequest() {
    return this.messages.map(({ role, content }) => ({ role, content }));
  }

  record(prompt, answer, task) {
    this.messages.push(
      { role: "user", content: prompt.slice(0, 6000), task },
      { role: "assistant", content: answer.slice(0, 6000), task },
    );
    this.messages = this.messages.slice(-this.maxMessages);
  }

  clear() {
    this.messages = [];
  }

  turnCount() {
    return this.messages.filter((message) => message.role === "user").length;
  }

  recentTurns() {
    return this.messages
      .filter((message) => message.role === "user")
      .map((message) => ({ task: message.task, content: message.content }));
  }
}
