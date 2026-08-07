package com.safewalk.mobile

import android.Manifest
import android.app.Activity.RESULT_OK
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.telephony.SmsManager
import android.telephony.SubscriptionManager
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : FlutterActivity() {
    companion object {
        private const val CHANNEL_NAME = "walksafe/device_sms"
        private const val SEND_SMS_PERMISSION_REQUEST_CODE = 4107
        private const val SMS_RESULT_TIMEOUT_MS = 20000L
    }

    private data class PendingSmsRequest(
        val phoneNumber: String,
        val message: String,
        val result: MethodChannel.Result,
    )

    private var pendingSmsRequest: PendingSmsRequest? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            CHANNEL_NAME,
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "sendSms" -> handleSendSms(call, result)
                else -> result.notImplemented()
            }
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        if (requestCode == SEND_SMS_PERMISSION_REQUEST_CODE) {
            val pendingRequest = pendingSmsRequest
            pendingSmsRequest = null

            if (pendingRequest != null) {
                if (grantResults.isNotEmpty() &&
                    grantResults[0] == PackageManager.PERMISSION_GRANTED
                ) {
                    sendSmsAndAwaitConfirmation(
                        phoneNumber = pendingRequest.phoneNumber,
                        message = pendingRequest.message,
                        result = pendingRequest.result,
                    )
                } else {
                    pendingRequest.result.error(
                        "PERMISSION_DENIED",
                        "SMS permission denied. WalkSafe cannot send device-local SOS alerts without it.",
                        null,
                    )
                }
            }
        }

        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
    }

    private fun handleSendSms(call: MethodCall, result: MethodChannel.Result) {
        val phoneNumber = call.argument<String>("phoneNumber")
        val message = call.argument<String>("message")

        if (phoneNumber.isNullOrBlank() || message.isNullOrBlank()) {
            result.error(
                "INVALID_ARGUMENTS",
                "Phone number and message are required to send SMS.",
                null,
            )
            return
        }

        if (!packageManager.hasSystemFeature(PackageManager.FEATURE_TELEPHONY)) {
            result.error(
                "UNSUPPORTED",
                "This device does not advertise SMS telephony support.",
                null,
            )
            return
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            sendSmsAndAwaitConfirmation(
                phoneNumber = phoneNumber,
                message = message,
                result = result,
            )
            return
        }

        pendingSmsRequest = PendingSmsRequest(
            phoneNumber = phoneNumber,
            message = message,
            result = result,
        )
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.SEND_SMS),
            SEND_SMS_PERMISSION_REQUEST_CODE,
        )
    }

    private fun sendSmsAndAwaitConfirmation(
        phoneNumber: String,
        message: String,
        result: MethodChannel.Result,
    ) {
        val smsManager = try {
            resolveSmsManager()
        } catch (error: Exception) {
            result.error("FAILED", "Failed to initialize SMS manager: ${error.message}", null)
            return
        }

        val messageParts = ArrayList(smsManager.divideMessage(message))
        if (messageParts.isEmpty()) {
            result.error("INVALID_ARGUMENTS", "SMS message content is empty.", null)
            return
        }

        val action = "$packageName.SMS_SENT.${System.currentTimeMillis()}"
        val filter = IntentFilter(action)
        val completed = AtomicBoolean(false)
        val failureReasons = mutableListOf<String>()
        var remainingParts = messageParts.size

        val timeoutHandler = Handler(Looper.getMainLooper())
        lateinit var receiver: BroadcastReceiver

        val timeoutRunnable = Runnable {
            if (!completed.compareAndSet(false, true)) {
                return@Runnable
            }

            unregisterReceiverSafely(receiver)
            result.error(
                "TIMEOUT",
                "Timed out waiting for Android to confirm the SMS send request.",
                null,
            )
        }

        receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (completed.get()) {
                    return
                }

                if (resultCode != RESULT_OK) {
                    failureReasons.add(mapSmsFailure(resultCode, intent))
                }

                remainingParts -= 1
                if (remainingParts > 0 || !completed.compareAndSet(false, true)) {
                    return
                }

                timeoutHandler.removeCallbacks(timeoutRunnable)
                unregisterReceiverSafely(this)

                if (failureReasons.isEmpty()) {
                    val detail = if (messageParts.size == 1) {
                        "SMS handed off to Android for delivery."
                    } else {
                        "Multipart SMS handed off to Android in ${messageParts.size} parts."
                    }
                    result.success(
                        mapOf(
                            "sent" to true,
                            "message" to detail,
                        ),
                    )
                } else {
                    result.error(
                        "FAILED",
                        failureReasons.distinct().joinToString(" "),
                        null,
                    )
                }
            }
        }

        registerSmsReceiver(receiver, filter)
        timeoutHandler.postDelayed(timeoutRunnable, SMS_RESULT_TIMEOUT_MS)

        try {
            val pendingIntentFlags =
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            val requestCodeBase = (System.currentTimeMillis() % 1000000L).toInt()
            val sentIntents =
                ArrayList<PendingIntent>(messageParts.size).apply {
                    repeat(messageParts.size) { index ->
                        add(
                            PendingIntent.getBroadcast(
                                this@MainActivity,
                                requestCodeBase + index,
                                Intent(action).putExtra("partIndex", index),
                                pendingIntentFlags,
                            ),
                        )
                    }
                }

            if (messageParts.size == 1) {
                smsManager.sendTextMessage(
                    phoneNumber,
                    null,
                    messageParts.first(),
                    sentIntents.first(),
                    null,
                )
            } else {
                smsManager.sendMultipartTextMessage(
                    phoneNumber,
                    null,
                    messageParts,
                    sentIntents,
                    null,
                )
            }
        } catch (error: Exception) {
            timeoutHandler.removeCallbacks(timeoutRunnable)
            if (completed.compareAndSet(false, true)) {
                unregisterReceiverSafely(receiver)
                result.error(
                    "FAILED",
                    "Android rejected the SMS request: ${error.message}",
                    null,
                )
            }
        }
    }

    private fun resolveSmsManager(): SmsManager {
        val defaultSubscriptionId = SubscriptionManager.getDefaultSmsSubscriptionId()
        return if (defaultSubscriptionId != SubscriptionManager.INVALID_SUBSCRIPTION_ID) {
            SmsManager.getSmsManagerForSubscriptionId(defaultSubscriptionId)
        } else {
            SmsManager.getDefault()
        }
    }

    private fun registerSmsReceiver(receiver: BroadcastReceiver, filter: IntentFilter) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(receiver, filter)
        }
    }

    private fun unregisterReceiverSafely(receiver: BroadcastReceiver) {
        try {
            unregisterReceiver(receiver)
        } catch (_: IllegalArgumentException) {
        }
    }

    private fun mapSmsFailure(resultCode: Int, intent: Intent?): String {
        val modemErrorCode = intent?.getIntExtra("errorCode", -1) ?: -1
        val reason = when (resultCode) {
            SmsManager.RESULT_ERROR_GENERIC_FAILURE ->
                "Carrier reported a generic SMS failure."
            SmsManager.RESULT_ERROR_NO_SERVICE ->
                "No mobile service was available to send the SMS."
            SmsManager.RESULT_ERROR_NULL_PDU ->
                "Android produced an invalid SMS payload."
            SmsManager.RESULT_ERROR_RADIO_OFF ->
                "The cellular radio was off while sending the SMS."
            else -> "Android failed to send the SMS (resultCode=$resultCode)."
        }

        return if (modemErrorCode >= 0) {
            "$reason Modem error code: $modemErrorCode."
        } else {
            reason
        }
    }
}
