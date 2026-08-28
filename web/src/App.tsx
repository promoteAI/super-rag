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
import DefaultModelsPage from './pages/DefaultModelsPage';

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
          <Route path="/settings" element={<DefaultModelsPage />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
