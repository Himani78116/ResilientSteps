import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../services/sos_service.dart';

class EmergencySosScreen extends StatefulWidget {
  const EmergencySosScreen({super.key});

  @override
  State<EmergencySosScreen> createState() => _EmergencySosScreenState();
}

class _EmergencySosScreenState extends State<EmergencySosScreen> {
  final SosService _sosService = SosService();
  bool _sending = false;

  Future<void> _sendEmergencyAlert() async {
    setState(() {
      _sending = true;
    });

    Position? position;
    try {
      position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      ).timeout(const Duration(seconds: 10));
    } catch (_) {
      position = null;
    }

    if (position == null) {
      if (mounted) {
        setState(() {
          _sending = false;
        });
        await showDialog<void>(
          context: context,
          barrierDismissible: false,
          builder: (_) => AlertDialog(
            title: const Text('Location required for SOS'),
            content: const Text(
              'WalkSafe needs your GPS location to send an accurate SOS alert.\n\n'
              'Please enable location permissions in your phone settings, then try again.\n\n'
              'If you need immediate help, call 112.',
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('OK'),
              ),
              TextButton(
                onPressed: () {
                  Navigator.of(context).pop();
                  Geolocator.openLocationSettings();
                },
                child: const Text('Open settings'),
              ),
            ],
          ),
        );
      }
      return;
    }

    final bool sent = await _sosService.sendEmergencyAlert(
      latitude: position.latitude,
      longitude: position.longitude,
    );
    if (!mounted) {
      return;
    }

    setState(() {
      _sending = false;
    });

    await showDialog<void>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(sent ? 'Alert Sent' : 'Alert Failed'),
          content: Text(
            sent
                ? 'Emergency SOS was sent to your trusted contacts.'
                : 'WalkSafe could not confirm the SMS send. Call local emergency services immediately.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('OK'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Emergency SOS')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            Icon(
              Icons.warning_amber_rounded,
              size: 100,
              color: Colors.red.shade700,
            ),
            const SizedBox(height: 20),
            const Text(
              'Press the button below to notify your emergency contacts.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 56,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.red.shade700,
                  foregroundColor: Colors.white,
                ),
                onPressed: _sending ? null : _sendEmergencyAlert,
                child: _sending
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.4,
                          color: Colors.white,
                        ),
                      )
                    : const Text(
                        'Send SOS Alert',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
