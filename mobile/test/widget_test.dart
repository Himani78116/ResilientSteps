import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart';
import 'package:mobile/screens/home_screen.dart';

void main() {
  testWidgets('App launches straight into HomeScreen (no splash)', (
    WidgetTester tester,
  ) async {
    // AuthGate renders HomeScreen directly; SplashScreen is no longer wired
    // into the launch path.
    await tester.pumpWidget(const WalkSafeApp());
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.image(const AssetImage('assets/f-logo.png')), findsNothing);
  });
}
