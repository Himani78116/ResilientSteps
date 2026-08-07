import 'package:flutter/material.dart';

import '../services/auth_service.dart';
import 'saved_places_screen.dart';
import 'trusted_contacts_screen.dart';

class SettingsProfileScreen extends StatefulWidget {
  const SettingsProfileScreen({super.key});

  @override
  State<SettingsProfileScreen> createState() => _SettingsProfileScreenState();
}

class _SettingsProfileScreenState extends State<SettingsProfileScreen> {
  bool _liveLocationSharing = true;
  bool _incidentNotifications = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings & Profile')),
      body: ListView(
        children: <Widget>[
          const SizedBox(height: 12),
          const ListTile(
            leading: CircleAvatar(child: Icon(Icons.person)),
            title: Text('Safety Settings'),
            subtitle: Text('Control your demo preferences and emergency setup'),
          ),
          const Divider(),
          SwitchListTile(
            value: _liveLocationSharing,
            title: const Text('Live Location Sharing'),
            subtitle: const Text('Share location with trusted contacts'),
            onChanged: (bool value) {
              setState(() {
                _liveLocationSharing = value;
              });
            },
          ),
          SwitchListTile(
            value: _incidentNotifications,
            title: const Text('Incident Notifications'),
            subtitle: const Text('Receive nearby safety updates'),
            onChanged: (bool value) {
              setState(() {
                _incidentNotifications = value;
              });
            },
          ),
          ListTile(
            leading: Icon(Icons.contact_phone_outlined),
            title: const Text('Trusted contacts'),
            subtitle: const Text('People notified when you use SOS'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute<void>(
                builder: (_) => const TrustedContactsScreen(),
              ),
            ),
          ),
          if (AuthService.instance.isLoggedIn)
            ListTile(
              leading: const Icon(Icons.place_outlined),
              title: const Text('Saved places'),
              subtitle: const Text('Home, Work, and favourites'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute<void>(
                  builder: (_) => const SavedPlacesScreen(),
                ),
              ),
            ),
          const ListTile(
            leading: Icon(Icons.privacy_tip_outlined),
            title: Text('Privacy Preferences'),
            subtitle: Text('Control data sharing and retention'),
            trailing: Icon(Icons.chevron_right),
          ),
          if (AuthService.instance.isLoggedIn)
            ListTile(
              leading: const Icon(Icons.logout, color: Colors.red),
              title: const Text(
                'Sign out',
                style: TextStyle(color: Colors.red),
              ),
              onTap: () async {
                final NavigatorState navigator = Navigator.of(context);
                final bool? confirm = await showDialog<bool>(
                  context: context,
                  builder: (BuildContext dialogContext) => AlertDialog(
                    title: const Text('Sign out?'),
                    content: const Text(
                      'You will need to sign in again to report incidents or use SOS.',
                    ),
                    actions: <Widget>[
                      TextButton(
                        onPressed: () => Navigator.of(dialogContext).pop(false),
                        child: const Text('Cancel'),
                      ),
                      ElevatedButton(
                        onPressed: () => Navigator.of(dialogContext).pop(true),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.red,
                        ),
                        child: const Text(
                          'Sign out',
                          style: TextStyle(color: Colors.white),
                        ),
                      ),
                    ],
                  ),
                );
                if (confirm == true) {
                  await AuthService.instance.signOut();
                  if (!mounted) {
                    return;
                  }
                  navigator.pop();
                }
              },
            ),
        ],
      ),
    );
  }
}
