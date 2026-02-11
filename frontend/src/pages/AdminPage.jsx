import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { services } from '../data/services';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { 
  LogOut, Search, Filter, Trash2, Eye, CheckCircle, 
  Clock, AlertCircle, BarChart3, RefreshCw, Loader2 
} from 'lucide-react';
import axios from 'axios';
import { Toaster, toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminPage = () => {
  const navigate = useNavigate();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [token, setToken] = useState('');
  const [loginData, setLoginData] = useState({ username: '', password: '' });
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  
  const [inquiries, setInquiries] = useState([]);
  const [stats, setStats] = useState({ total: 0, neu: 0, in_bearbeitung: 0, erledigt: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedInquiry, setSelectedInquiry] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    const savedToken = localStorage.getItem('adminToken');
    if (savedToken) {
      setToken(savedToken);
      setIsLoggedIn(true);
    }
  }, []);

  useEffect(() => {
    if (isLoggedIn && token) {
      fetchData();
    }
  }, [isLoggedIn, token]);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [inquiriesRes, statsRes] = await Promise.all([
        axios.get(`${API}/admin/inquiries`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/admin/stats`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setInquiries(inquiriesRes.data.inquiries || []);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      if (error.response?.status === 401) {
        handleLogout();
        toast.error('Sitzung abgelaufen. Bitte erneut anmelden.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoggingIn(true);
    try {
      const response = await axios.post(`${API}/admin/login`, loginData);
      setToken(response.data.token);
      localStorage.setItem('adminToken', response.data.token);
      setIsLoggedIn(true);
      toast.success('Erfolgreich angemeldet!');
    } catch (error) {
      console.error('Login error:', error);
      toast.error('Ungültige Anmeldedaten');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    setToken('');
    setIsLoggedIn(false);
    localStorage.removeItem('adminToken');
    setInquiries([]);
    setStats({ total: 0, neu: 0, in_bearbeitung: 0, erledigt: 0 });
  };

  const updateInquiryStatus = async (id, status) => {
    setIsUpdating(true);
    try {
      await axios.patch(`${API}/admin/inquiries/${id}`, { status }, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      fetchData();
      if (selectedInquiry?.id === id) {
        setSelectedInquiry({ ...selectedInquiry, status });
      }
      toast.success('Status aktualisiert');
    } catch (error) {
      console.error('Error updating inquiry:', error);
      toast.error('Fehler beim Aktualisieren');
    } finally {
      setIsUpdating(false);
    }
  };

  const updateInquiryNotes = async (id, notes) => {
    try {
      await axios.patch(`${API}/admin/inquiries/${id}`, { notes }, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      fetchData();
      toast.success('Notizen gespeichert');
    } catch (error) {
      console.error('Error updating notes:', error);
      toast.error('Fehler beim Speichern');
    }
  };

  const deleteInquiry = async (id) => {
    if (!window.confirm('Möchten Sie diese Anfrage wirklich löschen?')) return;
    try {
      await axios.delete(`${API}/admin/inquiries/${id}`, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      fetchData();
      if (selectedInquiry?.id === id) setSelectedInquiry(null);
      toast.success('Anfrage gelöscht');
    } catch (error) {
      console.error('Error deleting inquiry:', error);
      toast.error('Fehler beim Löschen');
    }
  };

  const filteredInquiries = inquiries.filter(inq => {
    const matchesSearch = inq.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         inq.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || inq.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    const styles = {
      neu: 'bg-blue-100 text-blue-700',
      in_bearbeitung: 'bg-yellow-100 text-yellow-700',
      erledigt: 'bg-green-100 text-green-700'
    };
    const labels = {
      neu: 'Neu',
      in_bearbeitung: 'In Bearbeitung',
      erledigt: 'Erledigt'
    };
    return (
      <span className={`px-2 py-1 text-xs font-medium rounded ${styles[status] || 'bg-gray-100 text-gray-700'}`}>
        {labels[status] || status}
      </span>
    );
  };

  const getServiceName = (serviceId) => {
    const service = services.find(s => s.id === serviceId);
    return service?.name || serviceId;
  };

  // Login Screen
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6" data-testid="admin-login">
        <Toaster position="top-center" richColors />
        <div className="bg-white p-8 w-full max-w-md shadow-lg">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
              <span className="text-[#C41E3A]">Admin</span> Login
            </h1>
            <p className="text-gray-500 mt-2">PowerCleanService Dashboard</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2">Benutzername</label>
              <Input
                type="text"
                value={loginData.username}
                onChange={(e) => setLoginData({ ...loginData, username: e.target.value })}
                placeholder="admin"
                required
                className="h-12"
                data-testid="admin-username"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Passwort</label>
              <Input
                type="password"
                value={loginData.password}
                onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                placeholder="••••••••"
                required
                className="h-12"
                data-testid="admin-password"
              />
            </div>
            <button
              type="submit"
              disabled={isLoggingIn}
              className="btn-primary w-full py-4 flex items-center justify-center gap-2"
              data-testid="admin-login-button"
            >
              {isLoggingIn ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  Anmelden...
                </>
              ) : (
                'Anmelden'
              )}
            </button>
          </form>

          <p className="text-center text-gray-400 text-sm mt-6">
            Standardzugang: admin / powerclean2024
          </p>
        </div>
      </div>
    );
  }

  // Admin Dashboard
  return (
    <div className="min-h-screen bg-gray-100" data-testid="admin-dashboard">
      <Toaster position="top-center" richColors />
      
      {/* Header */}
      <header className="bg-[#0A0A0A] text-white py-4 px-6 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
              <span className="text-[#C41E3A]">Power</span>CleanService Admin
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={fetchData}
              className="p-2 hover:bg-white/10 rounded transition-colors"
              title="Aktualisieren"
              data-testid="refresh-button"
            >
              <RefreshCw size={20} className={isLoading ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 transition-colors"
              data-testid="logout-button"
            >
              <LogOut size={18} />
              Abmelden
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-6">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8" data-testid="stats-section">
          <div className="bg-white p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 className="text-gray-400" size={20} />
              <span className="text-sm text-gray-500 uppercase tracking-wider">Gesamt</span>
            </div>
            <div className="text-3xl font-bold" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
              {stats.total}
            </div>
          </div>
          <div className="bg-white p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-2">
              <AlertCircle className="text-blue-500" size={20} />
              <span className="text-sm text-gray-500 uppercase tracking-wider">Neu</span>
            </div>
            <div className="text-3xl font-bold text-blue-600" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
              {stats.neu}
            </div>
          </div>
          <div className="bg-white p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-2">
              <Clock className="text-yellow-500" size={20} />
              <span className="text-sm text-gray-500 uppercase tracking-wider">In Bearbeitung</span>
            </div>
            <div className="text-3xl font-bold text-yellow-600" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
              {stats.in_bearbeitung}
            </div>
          </div>
          <div className="bg-white p-6 border border-gray-200">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle className="text-green-500" size={20} />
              <span className="text-sm text-gray-500 uppercase tracking-wider">Erledigt</span>
            </div>
            <div className="text-3xl font-bold text-green-600" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
              {stats.erledigt}
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white p-4 border border-gray-200 mb-6 flex flex-col md:flex-row gap-4" data-testid="filters-section">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
            <Input
              type="text"
              placeholder="Nach Name oder E-Mail suchen..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 h-10"
              data-testid="search-input"
            />
          </div>
          <div className="flex gap-2">
            {['all', 'neu', 'in_bearbeitung', 'erledigt'].map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  statusFilter === status
                    ? 'bg-[#C41E3A] text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
                data-testid={`filter-${status}`}
              >
                {status === 'all' ? 'Alle' : status === 'neu' ? 'Neu' : status === 'in_bearbeitung' ? 'In Bearbeitung' : 'Erledigt'}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Inquiries List */}
          <div className="lg:col-span-5 bg-white border border-gray-200" data-testid="inquiries-list">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-bold" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                Anfragen ({filteredInquiries.length})
              </h2>
            </div>
            <div className="max-h-[600px] overflow-y-auto">
              {isLoading ? (
                <div className="p-8 text-center text-gray-500">
                  <Loader2 className="animate-spin mx-auto mb-2" size={24} />
                  Laden...
                </div>
              ) : filteredInquiries.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  Keine Anfragen gefunden
                </div>
              ) : (
                filteredInquiries.map((inq) => (
                  <div
                    key={inq.id}
                    onClick={() => setSelectedInquiry(inq)}
                    className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
                      selectedInquiry?.id === inq.id ? 'bg-gray-50 border-l-4 border-l-[#C41E3A]' : ''
                    }`}
                    data-testid={`inquiry-item-${inq.id}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h3 className="font-medium">{inq.name}</h3>
                        <p className="text-sm text-gray-500">{inq.email}</p>
                      </div>
                      {getStatusBadge(inq.status)}
                    </div>
                    <div className="flex flex-wrap gap-1 mb-2">
                      {inq.services.slice(0, 2).map((s) => (
                        <span key={s} className="text-xs bg-gray-100 px-2 py-1">
                          {getServiceName(s)}
                        </span>
                      ))}
                      {inq.services.length > 2 && (
                        <span className="text-xs text-gray-500">+{inq.services.length - 2}</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400">
                      {new Date(inq.created_at).toLocaleDateString('de-DE', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Inquiry Detail */}
          <div className="lg:col-span-7 bg-white border border-gray-200" data-testid="inquiry-detail">
            {selectedInquiry ? (
              <>
                <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                  <h2 className="font-bold" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    Anfrage Details
                  </h2>
                  <div className="flex gap-2">
                    <button
                      onClick={() => deleteInquiry(selectedInquiry.id)}
                      className="p-2 text-red-500 hover:bg-red-50 transition-colors"
                      title="Löschen"
                      data-testid="delete-inquiry-button"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
                <div className="p-6 space-y-6 max-h-[600px] overflow-y-auto">
                  {/* Contact Info */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-3 uppercase tracking-wider">Kontakt</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-gray-400">Name</p>
                        <p className="font-medium">{selectedInquiry.name}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">E-Mail</p>
                        <a href={`mailto:${selectedInquiry.email}`} className="font-medium text-[#C41E3A]">
                          {selectedInquiry.email}
                        </a>
                      </div>
                      {selectedInquiry.phone && (
                        <div>
                          <p className="text-xs text-gray-400">Telefon</p>
                          <a href={`tel:${selectedInquiry.phone}`} className="font-medium">
                            {selectedInquiry.phone}
                          </a>
                        </div>
                      )}
                      {selectedInquiry.address && (
                        <div>
                          <p className="text-xs text-gray-400">Adresse</p>
                          <p className="font-medium">{selectedInquiry.address}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Services */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-3 uppercase tracking-wider">Gewünschte Leistungen</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedInquiry.services.map((s) => (
                        <span key={s} className="bg-[#C41E3A]/10 text-[#C41E3A] px-3 py-1 text-sm font-medium">
                          {getServiceName(s)}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Date/Time */}
                  {(selectedInquiry.preferred_date || selectedInquiry.preferred_time) && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 mb-3 uppercase tracking-wider">Wunschtermin</h3>
                      <p className="font-medium">
                        {selectedInquiry.preferred_date && new Date(selectedInquiry.preferred_date).toLocaleDateString('de-DE')}
                        {selectedInquiry.preferred_time && ` um ${selectedInquiry.preferred_time} Uhr`}
                      </p>
                    </div>
                  )}

                  {/* Description */}
                  {selectedInquiry.description && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 mb-3 uppercase tracking-wider">Beschreibung</h3>
                      <p className="text-gray-700 bg-gray-50 p-4">{selectedInquiry.description}</p>
                    </div>
                  )}

                  {/* Status Update */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-3 uppercase tracking-wider">Status ändern</h3>
                    <div className="flex gap-2">
                      {['neu', 'in_bearbeitung', 'erledigt'].map((status) => (
                        <button
                          key={status}
                          onClick={() => updateInquiryStatus(selectedInquiry.id, status)}
                          disabled={isUpdating || selectedInquiry.status === status}
                          className={`px-4 py-2 text-sm font-medium transition-colors ${
                            selectedInquiry.status === status
                              ? 'bg-[#C41E3A] text-white'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                          data-testid={`status-btn-${status}`}
                        >
                          {status === 'neu' ? 'Neu' : status === 'in_bearbeitung' ? 'In Bearbeitung' : 'Erledigt'}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Notes */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-3 uppercase tracking-wider">Notizen</h3>
                    <Textarea
                      value={selectedInquiry.notes || ''}
                      onChange={(e) => setSelectedInquiry({ ...selectedInquiry, notes: e.target.value })}
                      onBlur={() => updateInquiryNotes(selectedInquiry.id, selectedInquiry.notes)}
                      placeholder="Interne Notizen hinzufügen..."
                      rows={4}
                      className="resize-none"
                      data-testid="notes-textarea"
                    />
                  </div>

                  {/* Metadata */}
                  <div className="pt-4 border-t border-gray-200 text-sm text-gray-400">
                    Erstellt am: {new Date(selectedInquiry.created_at).toLocaleDateString('de-DE', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-400 p-8">
                <div className="text-center">
                  <Eye size={48} className="mx-auto mb-4 opacity-50" />
                  <p>Wählen Sie eine Anfrage aus der Liste</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminPage;
