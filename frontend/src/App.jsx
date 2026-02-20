import "@/index.css";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";

// Pages
import HomePage from "./pages/HomePage";
import ServicesPage from "./pages/ServicesPage";
import ServiceDetailPage from "./pages/ServiceDetailPage";
import InquiryPage from "./pages/InquiryPage";
import ContactPage from "./pages/ContactPage";
import AdminPage from "./pages/AdminPage";
import ImpressumPage from "./pages/ImpressumPage";
import DatenschutzPage from "./pages/DatenschutzPage";
import AGBPage from "./pages/AGBPage";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/leistungen" element={<ServicesPage />} />
          <Route path="/leistungen/:serviceId" element={<ServiceDetailPage />} />
          <Route path="/anfrage" element={<InquiryPage />} />
          <Route path="/kontakt" element={<ContactPage />} />
          <Route path="/pcs-verwaltung-2024" element={<AdminPage />} />
          <Route path="/impressum" element={<ImpressumPage />} />
          <Route path="/datenschutz" element={<DatenschutzPage />} />
          <Route path="/agb" element={<AGBPage />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
