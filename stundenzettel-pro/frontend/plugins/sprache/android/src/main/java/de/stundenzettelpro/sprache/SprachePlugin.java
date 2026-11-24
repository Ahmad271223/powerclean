package de.stundenzettelpro.sprache;

import android.Manifest;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import java.util.ArrayList;

/**
 * Spracheingabe auf Android – gedrückt halten zum Sprechen, loslassen = Text.
 *
 * Datenschutz: nur die Spracherkennung AUF DEM GERÄT (ab Android 12, createOnDeviceSpeechRecognizer). Gibt es sie nicht, wird nichts
 * aufgenommen und die App bittet ums Eintippen – die Aufnahme verlässt das Handy nie. Gespeichert wird nichts.
 */
@CapacitorPlugin(name = "Sprache", permissions = { @Permission(strings = { Manifest.permission.RECORD_AUDIO }, alias = "mikrofon") })
public class SprachePlugin extends Plugin {

    private static final String NICHT_AUF_GERAET =
        "Spracherkennung auf diesem Handy nicht möglich, ohne die Aufnahme zu versenden. Bitte den Text eintippen.";
    private static final String NICHTS_VERSTANDEN = "Nichts verstanden. Bitte noch einmal deutlich sprechen.";

    private SpeechRecognizer erkenner;
    private PluginCall beendenCall;
    private String zwischentext = "";
    private String endtext = null;
    private boolean fehlerOhneText = false;

    private boolean aufGeraetMoeglich() {
        return Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(getContext());
    }

    @PluginMethod
    public void status(PluginCall call) {
        JSObject r = new JSObject();
        boolean moeglich = aufGeraetMoeglich();
        PermissionState stand = getPermissionState("mikrofon");
        r.put("plattform", "android");
        r.put("engine", "android");
        r.put("modell", moeglich ? "android-geraet" : null);
        r.put("modellGroesseMB", 0);
        r.put("modellGeladen", moeglich);
        r.put("rueckfallAufGeraet", moeglich);
        r.put("mikrofon", stand == PermissionState.GRANTED ? "erlaubt" : (stand == PermissionState.DENIED ? "verweigert" : "unbekannt"));
        call.resolve(r);
    }

    /** Android bringt das Sprachmodell selbst mit (Systemeinstellung „Spracherkennung auf dem Gerät“). */
    @PluginMethod
    public void modellLaden(PluginCall call) {
        if (!aufGeraetMoeglich()) {
            call.reject(NICHT_AUF_GERAET);
            return;
        }
        JSObject r = new JSObject();
        r.put("modell", "android-geraet");
        call.resolve(r);
    }

    @PluginMethod
    public void aufnahmeStarten(PluginCall call) {
        if (getPermissionState("mikrofon") != PermissionState.GRANTED) {
            requestPermissionForAlias("mikrofon", call, "mikrofonErlaubnis");
            return;
        }
        starten(call);
    }

    @PermissionCallback
    private void mikrofonErlaubnis(PluginCall call) {
        if (getPermissionState("mikrofon") == PermissionState.GRANTED) {
            starten(call);
        } else {
            call.reject("Kein Zugriff aufs Mikrofon. Bitte in den Android-Einstellungen bei „Stundenzettel Pro“ erlauben.");
        }
    }

    private void starten(PluginCall call) {
        if (!aufGeraetMoeglich()) {
            call.reject(NICHT_AUF_GERAET);
            return;
        }
        getActivity().runOnUiThread(() -> {
            aufraeumen();
            zwischentext = "";
            endtext = null;
            fehlerOhneText = false;
            beendenCall = null;
            erkenner = SpeechRecognizer.createOnDeviceSpeechRecognizer(getContext());
            erkenner.setRecognitionListener(new Zuhoerer());
            Intent absicht = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            absicht.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            absicht.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "de-DE");
            absicht.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
            absicht.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
            absicht.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000);
            absicht.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 4000);
            erkenner.startListening(absicht);
            call.resolve();
        });
    }

    @PluginMethod
    public void aufnahmeBeenden(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            if (endtext != null || fehlerOhneText) {
                // Android hat nach einer Sprechpause schon selbst beendet
                liefern(call);
                return;
            }
            if (erkenner == null) {
                call.reject("Es läuft keine Aufnahme.");
                return;
            }
            beendenCall = call;
            erkenner.stopListening();
        });
    }

    @PluginMethod
    public void aufnahmeAbbrechen(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            aufraeumen();
            call.resolve();
        });
    }

    private void liefern(PluginCall call) {
        String text = endtext != null && !endtext.trim().isEmpty() ? endtext.trim() : zwischentext.trim();
        aufraeumen();
        if (text.isEmpty()) {
            call.reject(NICHTS_VERSTANDEN);
            return;
        }
        JSObject r = new JSObject();
        r.put("text", text);
        r.put("engine", "android");
        call.resolve(r);
    }

    private void aufraeumen() {
        if (erkenner != null) {
            erkenner.cancel();
            erkenner.destroy();
            erkenner = null;
        }
    }

    @Override
    protected void handleOnDestroy() {
        aufraeumen();
    }

    private static String erstes(Bundle ergebnisse) {
        if (ergebnisse == null) return "";
        ArrayList<String> treffer = ergebnisse.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        return treffer != null && !treffer.isEmpty() && treffer.get(0) != null ? treffer.get(0) : "";
    }

    private class Zuhoerer implements RecognitionListener {
        @Override public void onReadyForSpeech(Bundle params) {}
        @Override public void onBeginningOfSpeech() {}
        @Override public void onRmsChanged(float rmsdB) {}
        @Override public void onBufferReceived(byte[] buffer) {}
        @Override public void onEndOfSpeech() {}
        @Override public void onEvent(int eventType, Bundle params) {}

        @Override
        public void onPartialResults(Bundle teil) {
            String t = erstes(teil);
            if (!t.isEmpty()) zwischentext = t;
        }

        @Override
        public void onResults(Bundle ergebnisse) {
            endtext = erstes(ergebnisse);
            if (beendenCall != null) {
                PluginCall c = beendenCall;
                beendenCall = null;
                liefern(c);
            }
        }

        @Override
        public void onError(int fehler) {
            fehlerOhneText = true;
            if (beendenCall != null) {
                PluginCall c = beendenCall;
                beendenCall = null;
                liefern(c);
            }
        }
    }
}
