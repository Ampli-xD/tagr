import React, { useState, useEffect } from "react";
import { StatusBar } from "expo-status-bar";
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
} from "react-native";
import * as Font from "expo-font";
import { Ionicons } from "@expo/vector-icons";

// Import Modular Components and Constants
import { COLORS } from "./src/components/constants/theme";
import { api } from "./src/services/api";
import AuthScreen from "./src/screens/AuthScreen";
import GalleryScreen from "./src/screens/GalleryScreen";
import NotificationsScreen from "./src/screens/NotificationsScreen";
import PhotoDetailModal from "./src/components/PhotoDetailModal";

export default function App() {
  const [fontsLoaded, setFontsLoaded] = useState(false);
  const [activeTab, setActiveTab] = useState("auth"); // auth, gallery, notifications
  const [token, setToken] = useState(null);
  const [username, setUsername] = useState("");
  const [userId, setUserId] = useState(null);

  // Auth fields
  const [regUsername, setRegUsername] = useState("");
  const [regMobile, setRegMobile] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [loginMobile, setLoginMobile] = useState("");
  const [loginOtpSent, setLoginOtpSent] = useState(false);
  const [loginOtpCode, setLoginOtpCode] = useState("");

  // Data lists
  const [photos, setPhotos] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [friendSuggestions, setFriendSuggestions] = useState([]);
  const [friendsList, setFriendsList] = useState([]);
  const [loading, setLoading] = useState(false);

  // Lightbox selection
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [commentText, setCommentText] = useState("");

  // Load Custom Fonts
  useEffect(() => {
    async function loadFonts() {
      try {
        await Font.loadAsync({
          "Fraunces-Italic": require("./assets/fonts/Fraunces-Italic.ttf"),
          Oswald: require("./assets/fonts/Oswald.ttf"),
          Inter: require("./assets/fonts/Inter.ttf"),
        });
      } catch (e) {
        console.warn("Could not load custom fonts, using fallbacks:", e);
      } finally {
        setFontsLoaded(true);
      }
    }
    loadFonts();
    loadMockData(); // Prepopulate local fallback mock data
  }, []);

  const loadMockData = () => {
    setPhotos([
      {
        id: "1",
        people: "You, Ananya + 2",
        meta: "Uploaded by Ravi · 2h ago",
        imageUrl:
          "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80",
        tagsCount: 3,
        liked: true,
        tags: [
          {
            id: "t1",
            name: "Ananya Sharma",
            initial: "A",
            confidence: 92,
            x: 26,
            y: 78,
          },
          {
            id: "t2",
            name: "Yash Mehta",
            initial: "Y",
            confidence: 78,
            x: 106,
            y: 120,
          },
        ],
        comments: [
          { author: "Ananya", text: "This looks so cool!" },
          { author: "Ravi", text: "Monochrome vibe is perfect." },
        ],
      },
      {
        id: "2",
        people: "Meera's photo",
        meta: "1 day ago",
        imageUrl:
          "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=800&q=80",
        tagsCount: 1,
        liked: false,
        tags: [],
        comments: [],
      },
    ]);

    setNotifications([
      {
        id: "n1",
        text: "Ravi tagged you in a new photo",
        time: "2 hours ago",
        unread: true,
        image:
          "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=80&q=80",
      },
      {
        id: "n2",
        text: "Meera added a photo with you and 3 others",
        time: "1 day ago",
        unread: true,
        image:
          "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=80&q=80",
      },
      {
        id: "n3",
        text: "Yash sent you a friend request",
        time: "2 days ago",
        unread: false,
        image:
          "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?auto=format&fit=crop&w=80&q=80",
      },
    ]);

    setFriendSuggestions([
      {
        id: "s1",
        username: "Rohan Gupta",
        matchReason: "In 4 photos with you",
      },
      { id: "s2", username: "Kriti Sen", matchReason: "In 2 photos with you" },
    ]);

    setFriendsList([
      { id: "f1", username: "Ananya Sharma" },
      { id: "f2", username: "Yash Mehta" },
      { id: "f3", username: "Meera Nair" },
    ]);
  };

  // HTTP API call methods
  const fetchGallery = async () => {
    if (!token || !userId) return;
    setLoading(true);
    try {
      const res = await api.getGallery(userId, token);
      const data = await res.json();
      if (res.ok && data.photos) {
        const mapped = data.photos.map((p) => ({
          id: p.photo_id,
          people:
            p.tagged_users.length > 0
              ? `You, ${p.tagged_users.map((u) => u.username).join(", ")}`
              : "You",
          meta: `Uploaded at ${new Date(p.uploaded_at).toLocaleDateString()}`,
          imageUrl: p.url,
          tagsCount: p.tagged_users.length,
          liked: false,
          tags: p.tagged_users.map((u, idx) => ({
            id: u.user_id,
            name: u.username,
            initial: u.username ? u.username[0].toUpperCase() : "?",
            confidence: 90,
            x: 40 + idx * 40,
            y: 80 + idx * 30,
          })),
          comments: [],
        }));
        setPhotos(mapped);
      }
    } catch (e) {
      console.warn("Backend offline, relying on mock gallery data", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchNotifications = async () => {
    if (!token) return;
    try {
      const res = await api.getNotifications(token);
      const data = await res.json();
      if (res.ok && data.notifications) {
        const mapped = data.notifications.map((n) => ({
          id: n.notification_id,
          text: `${n.actor_username || "Someone"} tagged you in a new photo`,
          time: new Date(n.created_at).toLocaleDateString(),
          unread: !n.read,
          image:
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=80&q=80",
        }));
        setNotifications(mapped);
      }
    } catch (e) {
      console.warn("Backend offline, relying on mock notifications", e);
    }
  };

  const fetchFriendSuggestions = async () => {
    if (!token) return;
    try {
      const res = await api.getFriendSuggestions(token);
      const data = await res.json();
      if (res.ok && data.suggestions) {
        const mapped = data.suggestions.map((s) => ({
          id: s.user_id,
          username: s.username,
          matchReason: `Appeared in ${s.mutual_photo_count} mutual photos`,
        }));
        setFriendSuggestions(mapped);
      }
    } catch (e) {
      console.warn("Backend offline, relying on mock suggestions", e);
    }
  };

  const fetchFriendsList = async () => {
    if (!token) return;
    try {
      const res = await api.getFriendsList(token);
      const data = await res.json();
      if (res.ok && data.friends) {
        const mapped = data.friends.map((f) => ({
          id: f.user_id,
          username: f.username,
        }));
        setFriendsList(mapped);
      }
    } catch (e) {
      console.warn("Backend offline, relying on mock friends list", e);
    }
  };

  const handleSendFriendRequest = async (targetUserId) => {
    if (!token) return;
    try {
      const res = await api.sendFriendRequest(targetUserId, token);
      if (res.ok) {
        alert("Friend request sent!");
      } else {
        const data = await res.json();
        alert(data.detail || "Failed to send request");
      }
    } catch (e) {
      alert("Simulated Friend Request Sent!");
    }
  };

  useEffect(() => {
    if (token) {
      if (activeTab === "gallery") {
        fetchGallery();
      } else if (activeTab === "notifications") {
        fetchNotifications();
        fetchFriendSuggestions();
        fetchFriendsList();
      }
    }
  }, [activeTab, token]);

  // Auth screen handlers
  const handleRegister = async () => {
    if (!regUsername || !regMobile) return;
    setLoading(true);
    try {
      const res = await api.register(regUsername, regMobile);
      const data = await res.json();
      if (res.ok) {
        setUserId(data.user_id);
        setOtpSent(true);
        alert("OTP Code generated (Use 123456 to verify).");
      } else {
        alert(data.detail || "Registration failed");
      }
    } catch (e) {
      console.warn("Backend offline, registering mock user locally", e);
      setUserId("mock_user_123");
      setOtpSent(true);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (!otpCode) return;
    setLoading(true);
    try {
      const res = await api.verifyOtp(regMobile, otpCode);
      const data = await res.json();
      if (res.ok) {
        setToken(data.token);
        setUsername(regUsername);
        setActiveTab("gallery");
      } else {
        alert(data.detail || "OTP Verification failed");
      }
    } catch (e) {
      console.warn("Backend offline, logging in mock user", e);
      setToken("mock_jwt_token");
      setUsername(regUsername || "Guest");
      setActiveTab("gallery");
    } finally {
      setLoading(false);
    }
  };

  const handleLoginRequest = async () => {
    if (!loginMobile) return;
    setLoading(true);
    try {
      const res = await api.requestLoginOtp(loginMobile);
      if (res.ok) {
        setLoginOtpSent(true);
        alert("OTP sent (Use 123456 to login).");
      } else {
        const data = await res.json();
        alert(data.detail || "Login OTP request failed");
      }
    } catch (e) {
      console.warn("Backend offline, showing mock OTP login", e);
      setLoginOtpSent(true);
    } finally {
      setLoading(false);
    }
  };

  const handleLoginConfirm = async () => {
    if (!loginOtpCode) return;
    setLoading(true);
    try {
      const res = await api.login(loginMobile, loginOtpCode);
      const data = await res.json();
      if (res.ok) {
        setToken(data.token);
        setUserId(data.user_id);
        setUsername(data.username);
        setActiveTab("gallery");
      } else {
        alert(data.detail || "Login failed");
      }
    } catch (e) {
      console.warn("Backend offline, using mock login authorization", e);
      setToken("mock_jwt_token");
      setUserId("mock_user_123");
      setUsername("Ravi");
      setActiveTab("gallery");
    } finally {
      setLoading(false);
    }
  };

  const handleEnrollFace = async () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      alert("Face enrolled successfully!");
    }, 1500);
  };

  const handleLikePhoto = (id) => {
    setPhotos((prev) =>
      prev.map((p) => (p.id === id ? { ...p, liked: !p.liked } : p)),
    );
  };

  const handleSelectPhoto = async (photo) => {
    setSelectedPhoto(photo);
    if (!token) return;
    try {
      const res = await api.getPhotoDetails(photo.id, token);
      const data = await res.json();
      if (res.ok) {
        setSelectedPhoto({
          id: data.photo_id,
          people:
            data.tags.length > 0
              ? `You, ${data.tags.map((t) => t.username).join(", ")}`
              : "You",
          meta: photo.meta,
          imageUrl: data.url,
          tagsCount: data.tags.length,
          liked: photo.liked,
          tags: data.tags.map((t, idx) => ({
            id: t.tag_id,
            name: t.username,
            initial: t.username ? t.username[0].toUpperCase() : "?",
            confidence: t.confidence || 100,
            x: t.bbox.x || 40 + idx * 40,
            y: t.bbox.y || 80 + idx * 30,
          })),
          comments: data.comments.map((c) => ({
            author: c.username,
            text: c.text,
          })),
        });
      }
    } catch (e) {
      console.warn(
        "Backend offline, using local cache comments/tags details",
        e,
      );
    }
  };

  const handlePostComment = async () => {
    if (!commentText || !selectedPhoto) return;
    const newComment = { author: username || "You", text: commentText };
    setSelectedPhoto((prev) => ({
      ...prev,
      comments: [...(prev.comments || []), newComment],
    }));
    setCommentText("");

    if (!token) return;
    try {
      await api.postComment(selectedPhoto.id, commentText, token);
    } catch (e) {
      console.warn("Backend offline, comment saved locally", e);
    }
  };

  if (!fontsLoaded) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.white} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="light" />

      {/* Top Header Bar */}
      <View style={styles.header}>
        {token ? (
          <TouchableOpacity
            style={styles.headerButton}
            onPress={() => alert("Simulating photo upload...")}
          >
            <Ionicons name="add-outline" size={24} color={COLORS.white} />
          </TouchableOpacity>
        ) : (
          <View style={{ width: 24 }} />
        )}

        {token ? (
          <TouchableOpacity
            style={styles.headerButton}
            onPress={() => setActiveTab("notifications")}
          >
            <Ionicons
              name="notifications-outline"
              size={24}
              color={COLORS.white}
            />
          </TouchableOpacity>
        ) : (
          <View style={{ width: 24 }} />
        )}
      </View>

      {/* Scrollable Content Views */}
      <ScrollView contentContainerStyle={styles.contentContainer}>
        {activeTab === "auth" && (
          <AuthScreen
            token={token}
            otpSent={otpSent}
            regUsername={regUsername}
            setRegUsername={setRegUsername}
            regMobile={regMobile}
            setRegMobile={setRegMobile}
            otpCode={otpCode}
            setOtpCode={setOtpCode}
            handleRegister={handleRegister}
            handleVerifyOTP={handleVerifyOTP}
            loginMobile={loginMobile}
            setLoginMobile={setLoginMobile}
            loginOtpSent={loginOtpSent}
            loginOtpCode={loginOtpCode}
            setLoginOtpCode={setLoginOtpCode}
            handleLoginRequest={handleLoginRequest}
            handleLoginConfirm={handleLoginConfirm}
            handleEnrollFace={handleEnrollFace}
            loading={loading}
          />
        )}

        {activeTab === "gallery" && (
          <GalleryScreen
            photos={photos}
            handleSelectPhoto={handleSelectPhoto}
            handleLikePhoto={handleLikePhoto}
          />
        )}

        {activeTab === "notifications" && (
          <NotificationsScreen
            notifications={notifications}
            friendSuggestions={friendSuggestions}
            friendsList={friendsList}
            sendFriendRequest={handleSendFriendRequest}
          />
        )}
      </ScrollView>

      {/* Floating Bottom Nav */}
      {token && (
        <View style={styles.bottomNavContainer}>
          <View style={[styles.bottomNav, styles.glass]}>
            <TouchableOpacity
              onPress={() => setActiveTab("gallery")}
              style={[
                styles.bottomNavItem,
                activeTab === "gallery" && styles.bottomNavActiveItem,
              ]}
            >
              <Ionicons
                name="images-outline"
                size={20}
                color={activeTab === "gallery" ? COLORS.white : COLORS.gray50}
              />
              <Text
                style={[
                  styles.bottomNavText,
                  { fontFamily: "Oswald" },
                  activeTab === "gallery" && styles.bottomNavActiveText,
                ]}
              >
                GALLERY
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => setActiveTab("notifications")}
              style={[
                styles.bottomNavItem,
                activeTab === "notifications" && styles.bottomNavActiveItem,
              ]}
            >
              <Ionicons
                name="notifications-outline"
                size={20}
                color={
                  activeTab === "notifications" ? COLORS.white : COLORS.gray50
                }
              />
              <Text
                style={[
                  styles.bottomNavText,
                  { fontFamily: "Oswald" },
                  activeTab === "notifications" && styles.bottomNavActiveText,
                ]}
              >
                ALERTS
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => setActiveTab("auth")}
              style={[
                styles.bottomNavItem,
                activeTab === "auth" && styles.bottomNavActiveItem,
              ]}
            >
              <Ionicons
                name="person-outline"
                size={20}
                color={activeTab === "auth" ? COLORS.white : COLORS.gray50}
              />
              <Text
                style={[
                  styles.bottomNavText,
                  { fontFamily: "Oswald" },
                  activeTab === "auth" && styles.bottomNavActiveText,
                ]}
              >
                ME
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Lightbox details modal */}
      <PhotoDetailModal
        selectedPhoto={selectedPhoto}
        setSelectedPhoto={setSelectedPhoto}
        commentText={commentText}
        setCommentText={setCommentText}
        handlePostComment={handlePostComment}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.black,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: COLORS.black,
    justifyContent: "center",
    alignItems: "center",
  },
  header: {
    height: Platform.OS === "web" ? 70 : 100,
    paddingTop: Platform.OS === "web" ? 10 : 50,
    paddingHorizontal: 20,
    backgroundColor: COLORS.black,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.05)",
  },
  headerButton: {
    width: 36,
    height: 36,
    justifyContent: "center",
    alignItems: "center",
  },
  wordmark: {
    fontSize: 22,
    fontWeight: "900",
    color: COLORS.white,
    letterSpacing: -0.01,
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 100,
  },
  bottomNavContainer: {
    position: "absolute",
    bottom: 24,
    left: 20,
    right: 20,
    alignItems: "center",
    zIndex: 10,
  },
  bottomNav: {
    flexDirection: "row",
    width: "100%",
    height: 64,
    borderRadius: 100,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
    justifyContent: "space-around",
    alignItems: "center",
    paddingHorizontal: 10,
    backgroundColor: "rgba(10,10,10,0.85)",
  },
  bottomNavItem: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
  },
  bottomNavActiveItem: {
    transform: [{ scale: 1.05 }],
  },
  bottomNavText: {
    fontSize: 9,
    letterSpacing: 0.5,
    color: COLORS.gray50,
    marginTop: 4,
  },
  bottomNavActiveText: {
    color: COLORS.white,
    fontWeight: "700",
  },
});
