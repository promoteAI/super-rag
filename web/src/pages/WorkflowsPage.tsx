import WorkflowEditorPage from './WorkflowEditorPage';

export default function WorkflowsPage() {
  // 直接复用 WorkflowEditorPage，使 /workflows 路由就是完整的 Nodeflow 画布
  return <WorkflowEditorPage />;
}

