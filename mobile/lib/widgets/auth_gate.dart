import 'dart:async';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../screens/home_screen.dart';
import '../services/auth_service.dart';
import '../services/saved_places_service.dart';

/// Root widget that listens to auth state changes.
/// Always shows HomeScreen. Guests use it in partial-feature mode.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  late final StreamSubscription<AuthState> _authSubscription;

  @override
  void initState() {
    super.initState();
    _authSubscription = AuthService.instance.authStateChanges.listen((
      AuthState event,
    ) {
      if (!mounted) {
        return;
      }

      if (event.event == AuthChangeEvent.signedIn) {
        SavedPlacesService.instance.syncFromSupabase().catchError((_) {});
      }
      if (event.event == AuthChangeEvent.signedOut) {
        SavedPlacesService.instance.clearLocalCache().catchError((_) {});
      }

      setState(() {});
    });
  }

  @override
  void dispose() {
    _authSubscription.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => const HomeScreen();
}
