package dev.quiet.autolycus;

import android.content.Context;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;

import androidx.media3.exoplayer.DefaultRenderersFactory;
import androidx.media3.exoplayer.audio.AudioCapabilities;
import androidx.media3.exoplayer.audio.AudioOffloadSupport;
import androidx.media3.exoplayer.audio.AudioSink;
import androidx.media3.exoplayer.audio.DefaultAudioSink;

import java.util.List;

/** A Bluetooth route must receive decoded PCM, never encoded Dolby audio frames. */
@androidx.annotation.OptIn(markerClass = androidx.media3.common.util.UnstableApi.class)
final class NativePlayerAudioRoute {
    final boolean bluetooth;
    final String routeTypes;

    @SuppressWarnings("deprecation")
    NativePlayerAudioRoute(Context context) {
        AudioManager manager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        boolean activeBluetooth = false;
        StringBuilder types = new StringBuilder();
        try {
            android.media.AudioAttributes attributes =
                    new android.media.AudioAttributes.Builder()
                            .setUsage(android.media.AudioAttributes.USAGE_MEDIA)
                            .setContentType(android.media.AudioAttributes.CONTENT_TYPE_MOVIE)
                            .build();
            List<AudioDeviceInfo> devices = manager.getAudioDevicesForAttributes(attributes);
            for (AudioDeviceInfo device : devices) {
                int type = device.getType();
                if (types.length() > 0) types.append(',');
                types.append(type);
                if (type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP
                        || type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                        || type == AudioDeviceInfo.TYPE_BLE_HEADSET
                        || type == AudioDeviceInfo.TYPE_BLE_SPEAKER
                        || type == AudioDeviceInfo.TYPE_BLE_BROADCAST) activeBluetooth = true;
            }
        } catch (RuntimeException unavailable) {
            // Routing queries can be unavailable on customized TV firmware.
        }
        if (types.length() == 0) {
            try {
                activeBluetooth = manager.isBluetoothA2dpOn();
                types.append(activeBluetooth ? AudioDeviceInfo.TYPE_BLUETOOTH_A2DP : -1);
            } catch (RuntimeException unavailable) {
                types.append(-1);
            }
        }
        bluetooth = activeBluetooth;
        routeTypes = types.toString();
    }

    DefaultRenderersFactory renderers(Context context) {
        return new DefaultRenderersFactory(context) {
            @Override
            @SuppressWarnings("deprecation")
            protected AudioSink buildAudioSink(
                    Context context,
                    boolean enableFloatOutput,
                    boolean enableAudioTrackPlaybackParams) {
                if (!bluetooth)
                    return super.buildAudioSink(
                            context, enableFloatOutput, enableAudioTrackPlaybackParams);
                // In Media3 1.8, explicit capabilities are used only without a Context.
                return new DefaultAudioSink.Builder()
                        .setAudioCapabilities(AudioCapabilities.DEFAULT_AUDIO_CAPABILITIES)
                        .setEnableFloatOutput(false)
                        .setEnableAudioTrackPlaybackParams(false)
                        .setAudioOffloadSupportProvider(
                                (format, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED)
                        .build();
            }
        }.setEnableDecoderFallback(true);
    }
}
