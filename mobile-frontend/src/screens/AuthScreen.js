import React from "react";
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "../components/constants/theme";

export default function AuthScreen({
  token,
  otpSent,
  regUsername,
  setRegUsername,
  regMobile,
  setRegMobile,
  otpCode,
  setOtpCode,
  handleRegister,
  handleVerifyOTP,
  loginMobile,
  setLoginMobile,
  loginOtpSent,
  loginOtpCode,
  setLoginOtpCode,
  handleLoginRequest,
  handleLoginConfirm,
  handleEnrollFace,
  loading,
}) {
  return (
    <View style={styles.authContainer}>
      <View style={styles.heroSection}>
        <View style={styles.badgeIcon}>
          <Ionicons name="camera-outline" size={24} color={COLORS.white} />
        </View>
        <Text style={[styles.largeWordmark, { fontFamily: "Fraunces-Italic" }]}>
          tagr
        </Text>
        <Text style={styles.subtitle}>
          Look at the camera for a second. This is how friends' photos find you.
        </Text>
      </View>

      {/* Registration Form */}
      {!token && (
        <View style={styles.formCard}>
          <Text
            style={[styles.sectionTitle, { fontFamily: "Fraunces-Italic" }]}
          >
            Let's get you set up
          </Text>

          {!otpSent ? (
            <>
              <TextInput
                style={styles.input}
                placeholder="Username"
                placeholderTextColor={COLORS.gray50}
                value={regUsername}
                onChangeText={setRegUsername}
              />
              <TextInput
                style={styles.input}
                placeholder="Mobile Number"
                placeholderTextColor={COLORS.gray50}
                value={regMobile}
                onChangeText={setRegMobile}
                keyboardType="phone-pad"
              />
              <TouchableOpacity style={styles.button} onPress={handleRegister}>
                {loading ? (
                  <ActivityIndicator color={COLORS.black} />
                ) : (
                  <Text style={styles.buttonText}>Capture my face</Text>
                )}
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.infoText}>
                Enter verification code (Use 123456)
              </Text>
              <TextInput
                style={styles.input}
                placeholder="OTP Code"
                placeholderTextColor={COLORS.gray50}
                value={otpCode}
                onChangeText={setOtpCode}
                keyboardType="number-pad"
              />
              <TouchableOpacity style={styles.button} onPress={handleVerifyOTP}>
                {loading ? (
                  <ActivityIndicator color={COLORS.black} />
                ) : (
                  <Text style={styles.buttonText}>Confirm & Start</Text>
                )}
              </TouchableOpacity>
            </>
          )}
        </View>
      )}

      {/* Login Card */}
      {!token && !otpSent && (
        <View style={[styles.formCard, { marginTop: 24 }]}>
          <Text
            style={[styles.sectionTitle, { fontFamily: "Fraunces-Italic" }]}
          >
            Already registered?
          </Text>

          {!loginOtpSent ? (
            <>
              <TextInput
                style={styles.input}
                placeholder="Mobile Number"
                placeholderTextColor={COLORS.gray50}
                value={loginMobile}
                onChangeText={setLoginMobile}
                keyboardType="phone-pad"
              />
              <TouchableOpacity
                style={styles.buttonOutline}
                onPress={handleLoginRequest}
              >
                {loading ? (
                  <ActivityIndicator color={COLORS.white} />
                ) : (
                  <Text style={styles.buttonOutlineText}>Request OTP</Text>
                )}
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.infoText}>Enter OTP code (Use 123456)</Text>
              <TextInput
                style={styles.input}
                placeholder="OTP Code"
                placeholderTextColor={COLORS.gray50}
                value={loginOtpCode}
                onChangeText={setLoginOtpCode}
                keyboardType="number-pad"
              />
              <TouchableOpacity
                style={styles.button}
                onPress={handleLoginConfirm}
              >
                {loading ? (
                  <ActivityIndicator color={COLORS.black} />
                ) : (
                  <Text style={styles.buttonText}>Login</Text>
                )}
              </TouchableOpacity>
            </>
          )}
        </View>
      )}

      {/* Face Capture Section */}
      {token && (
        <View style={styles.formCard}>
          <Text
            style={[styles.sectionTitle, { fontFamily: "Fraunces-Italic" }]}
          >
            📸 Face Registration
          </Text>
          <Text style={styles.infoText}>
            Enrolling your face unlocks matches across the tagr platform.
          </Text>

          <View style={styles.cameraPlaceholder}>
            <View style={styles.faceOval} />
            <Text style={styles.cameraPlaceholderText}>
              Live Feed Simulation
            </Text>
          </View>

          <TouchableOpacity style={styles.button} onPress={handleEnrollFace}>
            {loading ? (
              <ActivityIndicator color={COLORS.black} />
            ) : (
              <Text style={styles.buttonText}>Enroll Face Vector</Text>
            )}
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  authContainer: {
    flex: 1,
    justifyContent: "center",
  },
  heroSection: {
    alignItems: "center",
    marginVertical: 40,
  },
  badgeIcon: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: COLORS.glassStrong,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 16,
  },
  largeWordmark: {
    fontSize: 52,
    fontWeight: "900",
    color: COLORS.white,
    letterSpacing: -0.02,
    marginBottom: 10,
  },
  subtitle: {
    fontFamily: "Inter",
    fontSize: 13,
    color: COLORS.gray50,
    textAlign: "center",
    paddingHorizontal: 30,
    lineHeight: 18,
  },
  formCard: {
    backgroundColor: COLORS.ink90,
    borderRadius: 24,
    padding: 24,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.05)",
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: COLORS.white,
    marginBottom: 16,
  },
  input: {
    fontFamily: "Inter",
    backgroundColor: "rgba(0,0,0,0.3)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)",
    borderRadius: 12,
    padding: 14,
    color: COLORS.white,
    fontSize: 14,
    marginBottom: 16,
  },
  button: {
    backgroundColor: COLORS.white,
    borderRadius: 100,
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8,
  },
  buttonText: {
    color: COLORS.black,
    fontWeight: "700",
    fontSize: 14.5,
  },
  buttonOutline: {
    backgroundColor: "transparent",
    borderWidth: 1.5,
    borderColor: "rgba(255,255,255,0.3)",
    borderRadius: 100,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8,
  },
  buttonOutlineText: {
    color: COLORS.white,
    fontWeight: "700",
    fontSize: 14.5,
  },
  infoText: {
    color: COLORS.gray50,
    fontSize: 13,
    marginBottom: 16,
    lineHeight: 18,
  },
  cameraPlaceholder: {
    width: "100%",
    aspectRatio: 4 / 3,
    backgroundColor: "#000",
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: "rgba(255,255,255,0.15)",
    borderStyle: "dashed",
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
    marginBottom: 20,
  },
  faceOval: {
    width: "50%",
    height: "70%",
    borderRadius: 100,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.5)",
    borderStyle: "dashed",
  },
  cameraPlaceholderText: {
    fontFamily: "Inter",
    position: "absolute",
    bottom: 12,
    color: COLORS.gray50,
    fontSize: 12,
  },
});
