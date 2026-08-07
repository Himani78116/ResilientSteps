import 'dart:async';
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// A trusted contact that the user has manually saved.
/// Sent with SOS alerts so the backend knows who to notify.
class TrustedContact {
  final String name;
  final String phone;

  const TrustedContact({required this.name, required this.phone});

  Map<String, dynamic> toJson() => <String, dynamic>{
    'name': name,
    'phone': phone,
  };

  factory TrustedContact.fromJson(Map<String, dynamic> json) => TrustedContact(
    name: json['name'] as String,
    phone: json['phone'] as String,
  );

  /// A contact is valid for SOS if it has a non-empty phone number.
  bool get isValid => phone.trim().isNotEmpty;
}

class TrustedContactsService {
  static const String _key = 'trusted_contacts_v1';
  static const int maxContacts = 3;
  static const String _encryptionKey = 'W@lkS@f3C0d3xS3cr3tK3y';

  static String _encrypt(String plaintext) {
    final List<int> bytes = utf8.encode(plaintext);
    final List<int> keyBytes = utf8.encode(_encryptionKey);
    final List<int> encrypted = List<int>.generate(bytes.length, (i) {
      return bytes[i] ^ keyBytes[i % keyBytes.length];
    });
    return base64.encode(encrypted);
  }

  static String _decrypt(String ciphertext) {
    final List<int> encrypted = base64.decode(ciphertext);
    final List<int> keyBytes = utf8.encode(_encryptionKey);
    final List<int> decrypted = List<int>.generate(encrypted.length, (i) {
      return encrypted[i] ^ keyBytes[i % keyBytes.length];
    });
    return utf8.decode(decrypted);
  }

  /// Load saved trusted contacts from local storage.
  /// Returns an empty list if none have been saved yet.
  static Future<List<TrustedContact>> load() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final String? encryptedRaw = prefs.getString(_key);
    if (encryptedRaw == null || encryptedRaw.isEmpty) {
      return <TrustedContact>[];
    }
    try {
      final String raw = _decrypt(encryptedRaw);
      final List<dynamic> list = jsonDecode(raw) as List<dynamic>;
      return list
          .map(
            (dynamic entry) =>
                TrustedContact.fromJson(entry as Map<String, dynamic>),
          )
          .toList();
    } catch (_) {
      // Fallback: if decryption fails, check if the string was stored as plaintext
      try {
        final List<dynamic> list = jsonDecode(encryptedRaw) as List<dynamic>;
        final List<TrustedContact> contacts = list
            .map(
              (dynamic entry) =>
                  TrustedContact.fromJson(entry as Map<String, dynamic>),
            )
            .toList();
        // Automatically save as encrypted for future loads
        unawaited(save(contacts));
        return contacts;
      } catch (_) {}
      return <TrustedContact>[];
    }
  }

  /// Save the given list of trusted contacts to local storage.
  /// Trims the list to maxContacts before saving.
  static Future<bool> save(List<TrustedContact> contacts) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final List<TrustedContact> trimmed = contacts.take(maxContacts).toList();
    final String plaintext = jsonEncode(trimmed.map((TrustedContact c) => c.toJson()).toList());
    final String encrypted = _encrypt(plaintext);
    return prefs.setString(_key, encrypted);
  }

  /// True if at least one valid contact has been saved.
  static Future<bool> hasContacts() async {
    final List<TrustedContact> contacts = await load();
    return contacts.any((TrustedContact c) => c.isValid);
  }
}
