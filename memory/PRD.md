# PowerCleanService Website PRD

## Original Problem Statement
Redesign einer professionellen Reinigungsunternehmen-Website für PowerCleanService aus Hannover. Der Kunde wünscht eine seriösere, modernere Seite mit perfekt strukturierten Seiten und eigenen Detailseiten für alle 14 Dienstleistungen inkl. Admin-Bereich für Anfragen.

## User Choices
- Design: Professionell & modern
- Farbschema: Rot (#C41E3A) / Schwarz beibehalten
- Kunden-Logos: KiK, Goldbeck, Leonhard Moll, CleanGarant beibehalten
- Admin-Bereich für Anfragen-Management
- 14 ausführliche Dienstleistungs-Detailseiten

## User Personas
1. **B2B-Entscheider**: Facility Manager, Hausverwaltungen, Bauleiter
2. **Kleinunternehmer**: Suchen zuverlässigen Reinigungspartner
3. **Admin/Mitarbeiter**: Bearbeitet eingehende Anfragen

## Core Requirements (Static)
- Homepage mit Hero, Services, Trust-Indikatoren
- 14 Service-Detailseiten mit ausführlichen Infos
- Anfrage-Formular mit Service-Auswahl
- Admin-Dashboard für Anfragen-Management
- Impressum, Datenschutz, AGB
- Floating Kontakt-Buttons (WhatsApp, Anruf)

## What's Been Implemented (Feb 2026)
### Frontend
- [x] Homepage mit Hero-Section, Services-Grid, Kunden-Logos, Über uns
- [x] Leistungen-Übersichtsseite mit Filter & Suche
- [x] 14 Service-Detailseiten (Baureinigung, Industriereinigung, etc.)
- [x] Anfrage-Formular mit Multi-Service-Auswahl
- [x] Kontakt-Seite mit Karte & Kontaktdaten
- [x] Admin-Login & Dashboard
- [x] Impressum, Datenschutz, AGB
- [x] Floating WhatsApp & Anruf-Buttons

### Backend
- [x] Inquiry CRUD API (/api/inquiries)
- [x] Admin Authentication mit JWT
- [x] Admin Stats API
- [x] Services API

## Architecture
- Frontend: React 19 + Tailwind CSS + Shadcn/UI
- Backend: FastAPI + MongoDB
- Auth: JWT-basiert für Admin

## Admin Credentials
- Username: admin
- Password: powerclean2024

## Prioritized Backlog
### P0 (Completed)
- Homepage, Services, Inquiry Form, Admin Dashboard

### P1 (Future)
- E-Mail-Benachrichtigung bei neuen Anfragen
- Bildergalerie für abgeschlossene Projekte
- Kundenbewertungen/Testimonials

### P2 (Nice-to-have)
- Google Maps Integration für Einsatzgebiet
- Live-Chat Widget
- Preisrechner für Standard-Leistungen
