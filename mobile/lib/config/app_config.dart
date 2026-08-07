/// Compile-time configuration injected via --dart-define.
/// All values are required. The app asserts they are non-empty at startup.
class AppConfig {
  AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL');

  static const String maptilerApiKey = String.fromEnvironment(
    'MAPTILER_API_KEY',
  );

  static const String supabaseUrl = String.fromEnvironment('SUPABASE_URL');

  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
  );
}
