import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:mobile/services/sos_service.dart';
import 'package:mobile/services/trusted_contacts_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
  });

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });

  test('normalizePhoneNumber strips formatting and preserves leading plus', () {
    expect(
      SosService.normalizePhoneNumber('+1 (555) 123-4567'),
      '+15551234567',
    );
    expect(SosService.normalizePhoneNumber(' (555) 222-3333 '), '5552223333');
    expect(SosService.normalizePhoneNumber(''), isEmpty);
    expect(SosService.isValidNormalizedPhoneNumber('+15551234567'), isTrue);
    expect(SosService.isValidNormalizedPhoneNumber('abc123'), isFalse);
  });

  test('sendInitialAlert uses the first 3 valid trusted contacts', () async {
    final List<Map<String, Object?>> sentMessages = <Map<String, Object?>>[];
    final SosService service = SosService(
      contactsLoader: () async => const <TrustedContact>[
        TrustedContact(name: 'Alice', phone: '+1 (555) 111-2222'),
        TrustedContact(name: '', phone: '555-333-4444'),
        TrustedContact(name: 'Bad', phone: 'abc'),
        TrustedContact(name: 'Carol', phone: ' (555) 777-8888 '),
        TrustedContact(name: 'Dana', phone: '5559990000'),
      ],
      locationLoader: () async => LatLng(12.34, 56.78),
      smsTransport:
          ({required String phoneNumber, required String message}) async {
            sentMessages.add(<String, Object?>{
              'phoneNumber': phoneNumber,
              'message': message,
            });
            return 'sent';
          },
      nowProvider: () => DateTime.parse('2026-04-07T10:20:30'),
    );
    addTearDown(service.dispose);

    final SosSendResult result = await service.sendInitialAlert();

    expect(result.anySent, isTrue);
    expect(result.sentRecipients, hasLength(3));
    expect(result.failedRecipients, isEmpty);
    expect(result.skippedRecipients, hasLength(1));
    expect(
      sentMessages.map((Map<String, Object?> call) => call['phoneNumber']),
      <String>['+15551112222', '5553334444', '5557778888'],
    );
    expect(
      result.messageBody,
      contains('Location: https://www.google.com/maps?q=12.340000,56.780000'),
    );
    expect(result.messageBody, contains('Time: 2026-04-07T10:20:30.000'));
  });

  test('sendInitialAlert reports missing location cleanly', () async {
    final SosService service = SosService(
      contactsLoader: () async => const <TrustedContact>[
        TrustedContact(name: 'Alice', phone: '5551234567'),
      ],
      locationLoader: () async => null,
      smsTransport:
          ({required String phoneNumber, required String message}) async {
            fail('SMS transport should not be called without a location.');
          },
    );
    addTearDown(service.dispose);

    final SosSendResult result = await service.sendInitialAlert();

    expect(result.anySent, isFalse);
    expect(result.locationUnavailable, isTrue);
    expect(
      result.generalError,
      contains('could not read your current GPS location'),
    );
    expect(service.currentState.kind, SosUiStatusKind.failed);
    expect(service.currentState.isActive, isFalse);
  });

  test('sendInitialAlert records SMS transport failures', () async {
    final SosService service = SosService(
      contactsLoader: () async => const <TrustedContact>[
        TrustedContact(name: 'Alice', phone: '5551234567'),
      ],
      locationLoader: () async => LatLng(12.34, 56.78),
      smsTransport:
          ({required String phoneNumber, required String message}) async {
            throw Exception('Carrier rejected the message');
          },
    );
    addTearDown(service.dispose);

    final SosSendResult result = await service.sendInitialAlert();

    expect(result.anySent, isFalse);
    expect(result.sentRecipients, isEmpty);
    expect(result.failedRecipients, hasLength(1));
    expect(
      result.failedRecipients.single.reason,
      'Carrier rejected the message',
    );
    expect(service.currentState.kind, SosUiStatusKind.failed);
  });
}
