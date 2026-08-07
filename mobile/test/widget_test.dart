import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart';

void main() {
  testWidgets('App launches and shows splash screen', (
    WidgetTester tester,
  ) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const WalkSafeApp());

    expect(find.text('WalkSafe'), findsOneWidget);
    expect(find.text('Safer routes for safer walks'), findsOneWidget);
  });
}
