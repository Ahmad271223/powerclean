/**
 * Fremde Bausteine der App mit Lizenz – angezeigt unter „Über / Lizenzen“.
 * Regel: nur freie Lizenzen ohne Copyleft (MIT, Apache 2.0, BSD; ISC ist inhaltlich gleich MIT).
 * `npm run lizenzen` prüft, dass jede Abhängigkeit aus package.json hier steht und eine erlaubte Lizenz hat.
 */
export const ERLAUBT = ['MIT', 'ISC', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause'];

export const BAUSTEINE = [
  { name: 'React', paket: 'react', lizenz: 'MIT', urheber: 'Meta Platforms, Inc.', adresse: 'https://github.com/facebook/react' },
  { name: 'React DOM', paket: 'react-dom', lizenz: 'MIT', urheber: 'Meta Platforms, Inc.', adresse: 'https://github.com/facebook/react' },
  { name: 'React Router', paket: 'react-router-dom', lizenz: 'MIT', urheber: 'Remix Software Inc.', adresse: 'https://github.com/remix-run/react-router' },
  { name: 'Capacitor Core', paket: '@capacitor/core', lizenz: 'MIT', urheber: 'Ionic', adresse: 'https://github.com/ionic-team/capacitor' },
  { name: 'Capacitor App', paket: '@capacitor/app', lizenz: 'MIT', urheber: 'Ionic', adresse: 'https://github.com/ionic-team/capacitor-plugins' },
  { name: 'Capacitor Push Notifications', paket: '@capacitor/push-notifications', lizenz: 'MIT', urheber: 'Ionic', adresse: 'https://github.com/ionic-team/capacitor-plugins' },
  { name: 'Capacitor Splash Screen', paket: '@capacitor/splash-screen', lizenz: 'MIT', urheber: 'Ionic', adresse: 'https://github.com/ionic-team/capacitor-plugins' },
  { name: 'Capacitor Status Bar', paket: '@capacitor/status-bar', lizenz: 'MIT', urheber: 'Ionic', adresse: 'https://github.com/ionic-team/capacitor-plugins' },
  { name: 'Radix UI Dialog', paket: '@radix-ui/react-dialog', lizenz: 'MIT', urheber: 'WorkOS', adresse: 'https://github.com/radix-ui/primitives' },
  { name: 'Lucide (Symbole)', paket: 'lucide-react', lizenz: 'ISC', urheber: 'Lucide Contributors', adresse: 'https://github.com/lucide-icons/lucide' },
  { name: 'jsPDF', paket: 'jspdf', lizenz: 'MIT', urheber: 'James Hall, yWorks GmbH', adresse: 'https://github.com/parallax/jsPDF' },
  { name: 'jsPDF-AutoTable', paket: 'jspdf-autotable', lizenz: 'MIT', urheber: 'Simon Bengtsson', adresse: 'https://github.com/simonbengtsson/jsPDF-AutoTable' },
  { name: 'DOMPurify (über jsPDF)', paket: null, lizenz: 'Apache-2.0', urheber: 'Cure53', adresse: 'https://github.com/cure53/DOMPurify', hinweis: 'doppelt lizenziert (MPL-2.0 oder Apache-2.0) – genutzt unter Apache-2.0' },
  { name: 'node-qrcode', paket: 'qrcode', lizenz: 'MIT', urheber: 'Ryan Day', adresse: 'https://github.com/soldair/node-qrcode' },
  { name: 'Sonner (Hinweise)', paket: 'sonner', lizenz: 'MIT', urheber: 'Emil Kowalski', adresse: 'https://github.com/emilkowalski/sonner' },
  { name: 'clsx', paket: 'clsx', lizenz: 'MIT', urheber: 'Luke Edwards', adresse: 'https://github.com/lukeed/clsx' },
  { name: 'tailwind-merge', paket: 'tailwind-merge', lizenz: 'MIT', urheber: 'Dany Castillo', adresse: 'https://github.com/dcastil/tailwind-merge' },
  { name: 'Tailwind CSS (Gestaltung, beim Bauen)', paket: null, lizenz: 'MIT', urheber: 'Tailwind Labs, Inc.', adresse: 'https://github.com/tailwindlabs/tailwindcss' },
];
