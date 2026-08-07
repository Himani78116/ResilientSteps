import 'package:flutter/material.dart';

import '../services/trusted_contacts_service.dart';

/// Screen where the user adds or edits their trusted emergency contacts.
/// Accessible from Settings. Contacts are stored on this device.
class TrustedContactsScreen extends StatefulWidget {
  const TrustedContactsScreen({super.key});

  @override
  State<TrustedContactsScreen> createState() => _TrustedContactsScreenState();
}

class _TrustedContactsScreenState extends State<TrustedContactsScreen> {
  List<TrustedContact> _contacts = <TrustedContact>[];
  List<TrustedContact> _lastSavedContacts = <TrustedContact>[];
  bool _loading = true;
  bool _saving = false;

  final List<TextEditingController> _nameControllers =
      List<TextEditingController>.generate(3, (_) => TextEditingController());
  final List<TextEditingController> _phoneControllers =
      List<TextEditingController>.generate(3, (_) => TextEditingController());

  @override
  void initState() {
    super.initState();
    _loadContacts();
  }

  Future<void> _loadContacts() async {
    final List<TrustedContact> saved = await TrustedContactsService.load();
    if (!mounted) {
      return;
    }

    for (int i = 0; i < 3; i++) {
      _nameControllers[i].text = i < saved.length ? saved[i].name : '';
      _phoneControllers[i].text = i < saved.length ? saved[i].phone : '';
    }

    setState(() {
      _contacts = saved;
      _lastSavedContacts = List<TrustedContact>.from(saved);
      _loading = false;
    });
  }

  List<TrustedContact> _collectContacts() {
    final List<TrustedContact> contacts = <TrustedContact>[];
    for (int i = 0; i < 3; i++) {
      final String name = _nameControllers[i].text.trim();
      final String phone = _phoneControllers[i].text.trim();
      if (name.isNotEmpty || phone.isNotEmpty) {
        contacts.add(TrustedContact(name: name, phone: phone));
      }
    }
    return contacts;
  }

  bool get _hasUnsavedChanges {
    final List<TrustedContact> current = _collectContacts();
    if (current.length != _lastSavedContacts.length) {
      return true;
    }

    for (int i = 0; i < current.length; i++) {
      if (current[i].name != _lastSavedContacts[i].name ||
          current[i].phone != _lastSavedContacts[i].phone) {
        return true;
      }
    }
    return false;
  }

  Future<bool> _save({bool showFeedback = true}) async {
    if (_saving) {
      return false;
    }

    setState(() {
      _saving = true;
    });

    final List<TrustedContact> contacts = _collectContacts();
    final bool saved = await TrustedContactsService.save(contacts);
    if (!mounted) {
      return saved;
    }

    setState(() {
      _contacts = contacts;
      _lastSavedContacts = List<TrustedContact>.from(contacts);
      _saving = false;
    });

    if (showFeedback) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            saved
                ? 'Trusted contacts saved.'
                : 'Could not save trusted contacts. Please try again.',
          ),
        ),
      );
    }

    return saved;
  }

  Future<bool> _handleBackNavigation() async {
    if (_saving) {
      return false;
    }

    if (!_hasUnsavedChanges) {
      return true;
    }

    final bool saved = await _save(showFeedback: false);
    if (!mounted) {
      return false;
    }

    if (!saved) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Could not save trusted contacts before leaving.'),
        ),
      );
      return false;
    }

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Trusted contacts saved.')));
    return true;
  }

  @override
  void dispose() {
    for (final TextEditingController controller in _nameControllers) {
      controller.dispose();
    }
    for (final TextEditingController controller in _phoneControllers) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return PopScope<Object?>(
      canPop: !_saving && !_hasUnsavedChanges,
      onPopInvokedWithResult: (bool didPop, Object? result) async {
        if (didPop || _saving || !_hasUnsavedChanges) {
          return;
        }

        final NavigatorState navigator = Navigator.of(context);
        final bool shouldPop = await _handleBackNavigation();
        if (shouldPop && mounted) {
          navigator.pop(result);
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Trusted Contacts'),
          actions: <Widget>[
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: TextButton.icon(
                onPressed: _saving ? null : _save,
                icon: _saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save_outlined),
                label: const Text('Save'),
              ),
            ),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: <Widget>[
            Text(
              _contacts.isEmpty
                  ? 'Add up to 3 trusted contacts. WalkSafe will send them device-local SOS text messages with your live location when you trigger an alert.'
                  : 'You can update up to 3 trusted contacts here. WalkSafe uses these names and phone numbers for SOS text alerts and live updates.',
              style: const TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 24),
            for (int i = 0; i < 3; i++) ...<Widget>[
              Text(
                'Contact ${i + 1}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _nameControllers[i],
                decoration: const InputDecoration(
                  labelText: 'Name',
                  border: OutlineInputBorder(),
                ),
                textCapitalization: TextCapitalization.words,
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _phoneControllers[i],
                decoration: const InputDecoration(
                  labelText: 'Phone number',
                  border: OutlineInputBorder(),
                ),
                keyboardType: TextInputType.phone,
              ),
              const SizedBox(height: 24),
            ],
            FilledButton.icon(
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.save_outlined),
              label: const Text('Save trusted contacts'),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              _hasUnsavedChanges
                  ? 'You have unsaved changes. Saving keeps these contacts available for SOS.'
                  : 'Saved contacts are available to the SOS flow immediately.',
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: const Color(0xFF617286)),
            ),
          ],
        ),
      ),
    );
  }
}
