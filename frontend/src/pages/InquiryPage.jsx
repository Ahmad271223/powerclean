import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { PageWrapper, Breadcrumb } from '../components/Layout';
import { services, companyInfo } from '../data/services';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import { CheckCircle, Phone, Mail, Clock, Send, Loader2 } from 'lucide-react';
import axios from 'axios';
import { Toaster, toast } from 'sonner';
const API = `${import.meta.env.VITE_BACKEND_URL || 'https://powerclean-backend.onrender.com'}/api`;
const InquiryPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const preselectedService = searchParams.get('service');

  const [formData, setFormData] = useState({
    services: preselectedService ? [preselectedService] : [],
    name: '',
    email: '',
    phone: '',
    address: '',
    preferred_date: '',
    preferred_time: '',
    description: '',
    consent: false
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const toggleService = (serviceId) => {
    setFormData(prev => ({
      ...prev,
      services: prev.services.includes(serviceId)
        ? prev.services.filter(s => s !== serviceId)
        : [...prev.services, serviceId]
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (formData.services.length === 0) {
      toast.error('Bitte wählen Sie mindestens eine Leistung aus.');
      return;
    }

    if (!formData.consent) {
      toast.error('Bitte stimmen Sie der Datenschutzerklärung zu.');
      return;
    }

    setIsSubmitting(true);

    try {
      await axios.post(`${API}/inquiries`, formData);
      setIsSuccess(true);
      toast.success('Ihre Anfrage wurde erfolgreich gesendet!');
    } catch (error) {
      console.error('Error submitting inquiry:', error);
      toast.error('Es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) {
    return (
      <PageWrapper>
        <Toaster position="top-center" richColors />
        <section className="min-h-[80vh] flex items-center justify-center py-24" data-testid="inquiry-success">
          <div className="max-w-lg mx-auto px-6 text-center">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-8">
              <CheckCircle className="text-green-600" size={40} />
            </div>
            <h1 className="text-4xl md:text-5xl mb-6">Vielen Dank!</h1>
            <p className="text-gray-600 text-lg mb-8">
              Ihre Anfrage wurde erfolgreich übermittelt. Wir melden uns innerhalb von 24 Stunden bei Ihnen.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button
                onClick={() => navigate('/')}
                className="btn-primary px-8 py-4"
                data-testid="success-home-button"
              >
                Zur Startseite
              </button>
              <button
                onClick={() => { setIsSuccess(false); setFormData({ ...formData, services: [], name: '', email: '', phone: '', address: '', preferred_date: '', preferred_time: '', description: '', consent: false }); }}
                className="btn-secondary px-8 py-4"
                data-testid="success-new-inquiry-button"
              >
                Neue Anfrage
              </button>
            </div>
          </div>
        </section>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper>
      <Toaster position="top-center" richColors />

      {/* Hero */}
      <section className="bg-[#0A0A0A] text-white py-24" data-testid="inquiry-hero">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <Breadcrumb items={[{ label: 'Anfrage' }]} />
          <h1 className="text-5xl md:text-6xl mb-6">Anfrage starten</h1>
          <p className="text-xl text-gray-400 max-w-2xl">
            Wählen Sie Leistungen, Termin & senden Sie Ihre Anfrage in Sekunden unverbindlich.
          </p>
        </div>
      </section>

      {/* Form */}
      <section className="py-16 lg:py-24 bg-white" data-testid="inquiry-form-section">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
            {/* Form */}
            <div className="lg:col-span-8">
              <form onSubmit={handleSubmit} className="space-y-8" data-testid="inquiry-form">
                {/* Services Selection */}
                <div>
                  <Label className="text-lg font-bold mb-4 block" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    Leistungen auswählen *
                  </Label>
                  <div className="flex flex-wrap gap-3">
                    {services.map((service) => (
                      <button
                        key={service.id}
                        type="button"
                        onClick={() => toggleService(service.id)}
                        className={`px-4 py-2 text-sm font-medium transition-all border ${formData.services.includes(service.id)
                            ? 'bg-[#C41E3A] text-white border-[#C41E3A]'
                            : 'bg-white text-gray-700 border-gray-300 hover:border-[#C41E3A]'
                          }`}
                        data-testid={`service-toggle-${service.id}`}
                      >
                        {service.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Contact Info */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <Label htmlFor="name" className="mb-2 block">Name *</Label>
                    <Input
                      id="name"
                      type="text"
                      placeholder="Max Mustermann"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                      className="h-12"
                      data-testid="input-name"
                    />
                  </div>
                  <div>
                    <Label htmlFor="email" className="mb-2 block">E-Mail *</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="max@example.com"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      required
                      className="h-12"
                      data-testid="input-email"
                    />
                  </div>
                  <div>
                    <Label htmlFor="phone" className="mb-2 block">Telefon</Label>
                    <Input
                      id="phone"
                      type="tel"
                      placeholder="+49 ..."
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="h-12"
                      data-testid="input-phone"
                    />
                  </div>
                  <div>
                    <Label htmlFor="address" className="mb-2 block">Adresse</Label>
                    <Input
                      id="address"
                      type="text"
                      placeholder="Straße Nr., PLZ Ort"
                      value={formData.address}
                      onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                      className="h-12"
                      data-testid="input-address"
                    />
                  </div>
                </div>

                {/* Date & Time */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <Label htmlFor="date" className="mb-2 block">Wunschtermin (Datum)</Label>
                    <Input
                      id="date"
                      type="date"
                      value={formData.preferred_date}
                      onChange={(e) => setFormData({ ...formData, preferred_date: e.target.value })}
                      className="h-12"
                      data-testid="input-date"
                    />
                  </div>
                  <div>
                    <Label htmlFor="time" className="mb-2 block">Uhrzeit</Label>
                    <Input
                      id="time"
                      type="time"
                      value={formData.preferred_time}
                      onChange={(e) => setFormData({ ...formData, preferred_time: e.target.value })}
                      className="h-12"
                      data-testid="input-time"
                    />
                  </div>
                </div>

                {/* Description */}
                <div>
                  <Label htmlFor="description" className="mb-2 block">Objektbeschreibung (optional)</Label>
                  <Textarea
                    id="description"
                    placeholder="Größe, Besonderheiten, Zugang, Fotos etc."
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={5}
                    className="resize-none"
                    data-testid="input-description"
                  />
                </div>

                {/* Consent */}
                <div className="flex items-start gap-3">
                  <Checkbox
                    id="consent"
                    checked={formData.consent}
                    onCheckedChange={(checked) => setFormData({ ...formData, consent: checked })}
                    data-testid="checkbox-consent"
                  />
                  <Label htmlFor="consent" className="text-sm text-gray-600 cursor-pointer">
                    Ich stimme zu, dass meine Daten zur Kontaktaufnahme verwendet werden.
                    Weitere Informationen finden Sie in unserer{' '}
                    <a href="/datenschutz" className="text-[#C41E3A] hover:underline">Datenschutzerklärung</a>.
                  </Label>
                </div>

                {/* Submit */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="btn-primary w-full md:w-auto px-12 py-4 text-lg flex items-center justify-center gap-2"
                  data-testid="submit-button"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      Wird gesendet...
                    </>
                  ) : (
                    <>
                      <Send size={20} />
                      Anfrage senden
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* Sidebar */}
            <div className="lg:col-span-4">
              <div className="sticky top-28 space-y-8">
                {/* Why Us */}
                <div className="bg-gray-50 p-6 border border-gray-200" data-testid="inquiry-sidebar-why">
                  <h3 className="text-xl font-bold mb-4" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    Warum wir?
                  </h3>
                  <ul className="space-y-3 text-sm text-gray-600">
                    <li className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-[#C41E3A] mt-0.5 flex-shrink-0" />
                      Transparente Prozesse & schneller Rückruf
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-[#C41E3A] mt-0.5 flex-shrink-0" />
                      Deutsches Handwerk seit {companyInfo.since}
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-[#C41E3A] mt-0.5 flex-shrink-0" />
                      Versichert, zuverlässig, professionell
                    </li>
                  </ul>
                </div>

                {/* Direct Contact */}
                <div className="bg-[#0A0A0A] text-white p-6" data-testid="inquiry-sidebar-contact">
                  <h3 className="text-xl font-bold mb-4" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    Direktkontakt
                  </h3>
                  <div className="space-y-4">
                    <a
                      href={`tel:${companyInfo.phone}`}
                      className="flex items-center gap-3 text-gray-300 hover:text-white transition-colors"
                    >
                      <Phone size={20} className="text-[#C41E3A]" />
                      <span>{companyInfo.phone}</span>
                    </a>
                    <a
                      href={`mailto:${companyInfo.email}`}
                      className="flex items-center gap-3 text-gray-300 hover:text-white transition-colors"
                    >
                      <Mail size={20} className="text-[#C41E3A]" />
                      <span>{companyInfo.email}</span>
                    </a>
                    <div className="flex items-center gap-3 text-gray-300">
                      <Clock size={20} className="text-[#C41E3A]" />
                      <span>Mo-Fr: 7:00 - 18:00</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
};

export default InquiryPage;
