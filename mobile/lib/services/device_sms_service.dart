import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:sms_sender/sms_sender.dart';

class DeviceSmsService {
  static const MethodChannel _channel = MethodChannel('walksafe/device_sms');

  static bool get _isAndroid =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  static bool get _isIos =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;

  static Future<String> sendSms({
    required String phoneNumber,
    required String message,
  }) async {
    if (_isAndroid) {
      final Map<Object?, Object?>? response = await _channel
          .invokeMapMethod<Object?, Object?>('sendSms', <String, dynamic>{
            'phoneNumber': phoneNumber,
            'message': message,
          });

      final bool sent = response?['sent'] == true;
      final String detail =
          (response?['message'] as String?)?.trim().isNotEmpty == true
          ? (response!['message'] as String).trim()
          : 'SMS dispatch completed.';

      if (!sent) {
        throw Exception(detail);
      }

      return detail;
    }

    if (_isIos) {
      return SmsSender.sendSms(phoneNumber: phoneNumber, message: message);
    }

    throw UnsupportedError('SMS is only supported on Android and iOS.');
  }
}
