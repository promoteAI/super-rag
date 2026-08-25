/**
 * AG-UI protocol chat panel using CopilotKit.
 * Connects to POST /api/v1/agents/{agentId}/chats/{chatId}/ag-ui for streaming.
 * Includes human-in-the-loop example: confirm_before_destructive_action.
 */
import { CopilotKit, useCopilotAction } from '@copilotkit/react-core';
import { CopilotChat } from '@copilotkit/react-ui';
import '@copilotkit/react-ui/styles.css';

const getApiBase = (): string => {
  const base = typeof window !== 'undefined' ? window.location.origin : '';
  return base || '';
};

interface AgUiChatPanelProps {
  agentId: string;
  chatId: string;
}

function AgUiChatWithActions() {
  useCopilotAction({
    name: 'confirm_before_destructive_action',
    description: 'Ask the user to confirm a destructive or sensitive action (e.g. delete, overwrite). Call this before performing the action.',
    parameters: [
      { name: 'action', type: 'string', description: 'Short action name, e.g. delete_file' },
      { name: 'message', type: 'string', description: 'Message to show the user' },
      { name: 'details', type: 'string', description: 'Optional extra details' },
    ],
    handler: async ({ action, message, details }) => {
      const fullMessage = details ? `${message}\n\n${details}` : message;
      const confirmed = typeof window !== 'undefined' && window.confirm(fullMessage || `Confirm: ${action}?`);
      return { confirmed: !!confirmed, action };
    },
  });
  return (
    <div className="ag-ui-chat-container" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CopilotChat
        labels={{
          title: 'AI 助手',
          initial: '有什么可以帮你？',
        }}
      />
    </div>
  );
}

export function AgUiChatPanel({ agentId, chatId }: AgUiChatPanelProps) {
  const runtimeUrl = `${getApiBase()}/api/v1/agents/${agentId}/chats/${chatId}/ag-ui`;

  return (
    <CopilotKit runtimeUrl={runtimeUrl}>
      <AgUiChatWithActions />
    </CopilotKit>
  );
}
