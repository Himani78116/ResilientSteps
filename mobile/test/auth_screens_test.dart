import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/screens/login_screen.dart';
import 'package:mobile/screens/signup_screen.dart';

void main() {
  group('LoginScreen Widget Tests', () {
    testWidgets('renders on narrow mobile screen without overflow', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        const MaterialApp(
          home: LoginScreen(),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Welcome back'), findsOneWidget);
      expect(
        find.text('Sign in to access your routes and safety reports'),
        findsOneWidget,
      );
      expect(find.byType(TextFormField), findsNWidgets(2));
      expect(find.text('Sign in'), findsOneWidget);
      expect(find.text('Continue as guest'), findsOneWidget);
      expect(find.text('Sign up'), findsOneWidget);
      expect(find.image(const AssetImage('assets/f-logo.png')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('renders on wide desktop screen with max width constraint', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(1280, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        const MaterialApp(
          home: LoginScreen(),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.image(const AssetImage('assets/f-logo.png')), findsOneWidget);

      final Size emailFieldSize = tester.getSize(
        find.widgetWithText(TextFormField, 'Email address'),
      );
      // Ensure the field is bounded to the desktop container width (<= 540)
      expect(emailFieldSize.width, lessThanOrEqualTo(540));
      expect(emailFieldSize.height, inInclusiveRange(44.0, 56.0));
      expect(tester.takeException(), isNull);
    });

    testWidgets('fits a short laptop viewport without scrolling to two-pane', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(1024, 600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        const MaterialApp(
          home: LoginScreen(),
        ),
      );
      await tester.pumpAndSettle();

      // Two-pane mode shows the brand bullets.
      expect(
        find.text('Routes that weigh shade, heat, and incident zones'),
        findsOneWidget,
      );

      // The most-bottom element must sit inside the viewport at rest.
      final Rect signupRect = tester.getRect(find.text('Sign up'));
      expect(signupRect.bottom, lessThanOrEqualTo(600));
      expect(tester.takeException(), isNull);
    });
  });

  group('SignupScreen Widget Tests', () {
    testWidgets('renders on narrow mobile screen without overflow', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        const MaterialApp(
          home: SignupScreen(),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Create your account'), findsOneWidget);
      expect(
        find.text('Save places and unlock SOS + reporting'),
        findsOneWidget,
      );
      expect(find.byType(TextFormField), findsNWidgets(4));
      expect(find.text('Create account'), findsOneWidget);
      expect(find.text('Sign in'), findsOneWidget);
      expect(find.image(const AssetImage('assets/f-logo.png')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('renders on wide desktop screen with compact width', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(1280, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        const MaterialApp(
          home: SignupScreen(),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Create your account'), findsOneWidget);
      expect(find.image(const AssetImage('assets/f-logo.png')), findsOneWidget);

      final Size nameFieldSize = tester.getSize(
        find.widgetWithText(TextFormField, 'Display name'),
      );
      expect(nameFieldSize.width, lessThanOrEqualTo(540));
      expect(nameFieldSize.height, inInclusiveRange(44.0, 56.0));
      expect(tester.takeException(), isNull);
    });

    testWidgets('fits a short laptop viewport without scrolling to two-pane', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(1024, 600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        const MaterialApp(
          home: SignupScreen(),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.text('Routes that weigh shade, heat, and incident zones'),
        findsOneWidget,
      );

      final Rect signinRect = tester.getRect(find.text('Sign in'));
      expect(signinRect.bottom, lessThanOrEqualTo(600));
      expect(tester.takeException(), isNull);
    });
  });
}
