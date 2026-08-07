import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/screens/trusted_contacts_screen.dart';
import 'package:mobile/services/trusted_contacts_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test(
    'trusted contacts save/load keeps phone-only entries available',
    () async {
      final bool saved =
          await TrustedContactsService.save(const <TrustedContact>[
            TrustedContact(name: '', phone: '5551234567'),
            TrustedContact(name: 'Alice', phone: '+1 555 000 1111'),
          ]);

      final List<TrustedContact> loaded = await TrustedContactsService.load();

      expect(saved, isTrue);
      expect(loaded, hasLength(2));
      expect(loaded.first.name, isEmpty);
      expect(loaded.first.phone, '5551234567');
      expect(await TrustedContactsService.hasContacts(), isTrue);
    },
  );

  testWidgets('trusted contacts screen saves and reloads entered values', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: TrustedContactsScreen()));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).at(0), 'Alice');
    await tester.enterText(find.byType(TextField).at(1), '5551234567');
    await tester.scrollUntilVisible(
      find.text('Save trusted contacts'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Save trusted contacts'));
    await tester.pumpAndSettle();

    final List<TrustedContact> saved = await TrustedContactsService.load();
    expect(saved, hasLength(1));
    expect(saved.first.name, 'Alice');
    expect(saved.first.phone, '5551234567');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();

    await tester.pumpWidget(const MaterialApp(home: TrustedContactsScreen()));
    await tester.pumpAndSettle();

    expect(find.text('Alice'), findsOneWidget);
    expect(find.text('5551234567'), findsOneWidget);
  });
}
