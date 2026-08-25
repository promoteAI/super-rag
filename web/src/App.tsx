import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import CollectionsPage from './pages/CollectionsPage';
import CollectionDetailPage from './pages/CollectionDetailPage';
import MarketplacePage from './pages/MarketplacePage';
import ChatsPage from './pages/ChatsPage';
import BotsPage from './pages/BotsPage';
import AuthPage from './pages/AuthPage';
import ModelProvidersPage from './pages/ModelProvidersPage';
import ModelProviderModelsPage from './pages/ModelProviderModelsPage';
import WorkflowsPage from './pages/WorkflowsPage';
import WorkflowEditorPage from './pages/WorkflowEditorPage';
import NodeManagerPage from './pages/NodeManagerPage';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/login" element={<AuthPage />} />
          <Route path="/register" element={<AuthPage />} />
          <Route path="/" element={<CollectionsPage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/marketplace/collections/:id" element={<CollectionDetailPage />} />
          <Route path="/collections" element={<CollectionsPage />} />
          <Route path="/collections/:id" element={<CollectionDetailPage />} />
          <Route path="/bots" element={<BotsPage />} />
          <Route path="/chats" element={<ChatsPage />} />
          <Route path="/chats/:chatId" element={<ChatsPage />} />
          <Route path="/model-providers" element={<ModelProvidersPage />} />
          <Route path="/model-providers/:providerName/models" element={<ModelProviderModelsPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/workflows/:id" element={<WorkflowEditorPage />} />
          <Route path="/node-manager" element={<NodeManagerPage />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
