// Browser-side pointer to server-owned conversation and active circuit state.

export class ConversationSession {
  constructor(storage = window.sessionStorage) {
    // Conversation pointers are intentionally memory-only. Remove data written
    // by older versions so reopening the page always starts a fresh session.
    storage.removeItem('loomq.conversationSession');
    this.state = { conversationId: null, artifact: null };
  }

  requestContext() {
    const payload = {};
    if (this.state.conversationId) payload.conversation_id = this.state.conversationId;
    if (this.state.artifact?.id) {
      payload.active_artifact_id = this.state.artifact.id;
      payload.expected_version = this.state.artifact.version;
    }
    return payload;
  }

  update(response) {
    this.state = {
      conversationId: response.conversation_id || this.state.conversationId || null,
      artifact: response.active_artifact || null,
    };
    return this.state;
  }

  clear() {
    this.state = { conversationId: null, artifact: null };
  }
}
