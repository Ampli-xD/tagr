import { Platform } from "react-native";

export const API_BASE =
  Platform.OS === "web"
    ? "http://localhost:8787/api/v1"
    : "http://192.168.1.5:8787/api/v1"; // Android emulator local loopback

// Helper for auth headers
const getHeaders = (token) => {
  const headers = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

export const api = {
  // Authentication
  register: async (username, mobileNumber) => {
    const formData = new FormData();
    formData.append("username", username);
    formData.append("mobile_number", mobileNumber);
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      body: formData,
    });
    return res;
  },

  verifyOtp: async (mobileNumber, otp) => {
    const formData = new FormData();
    formData.append("mobile_number", mobileNumber);
    formData.append("otp", otp);
    const res = await fetch(`${API_BASE}/auth/verify-otp`, {
      method: "POST",
      body: formData,
    });
    return res;
  },

  requestLoginOtp: async (mobileNumber) => {
    const formData = new FormData();
    formData.append("mobile_number", mobileNumber);
    const res = await fetch(`${API_BASE}/auth/request-login-otp`, {
      method: "POST",
      body: formData,
    });
    return res;
  },

  login: async (mobileNumber, otp) => {
    const formData = new FormData();
    formData.append("mobile_number", mobileNumber);
    formData.append("otp", otp);
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      body: formData,
    });
    return res;
  },

  // Photos & Gallery
  getGallery: async (userId, token) => {
    return fetch(`${API_BASE}/users/${userId}/gallery`, {
      headers: getHeaders(token),
    });
  },

  getPhotoDetails: async (photoId, token) => {
    return fetch(`${API_BASE}/photos/${photoId}`, {
      headers: getHeaders(token),
    });
  },

  postComment: async (photoId, text, token) => {
    return fetch(`${API_BASE}/photos/${photoId}/comments`, {
      method: "POST",
      headers: {
        ...getHeaders(token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text }),
    });
  },

  // Social & Friend Requests
  getNotifications: async (token) => {
    return fetch(`${API_BASE}/notifications`, {
      headers: getHeaders(token),
    });
  },

  getFriendSuggestions: async (token) => {
    return fetch(`${API_BASE}/friends/suggestions`, {
      headers: getHeaders(token),
    });
  },

  getFriendsList: async (token) => {
    return fetch(`${API_BASE}/friends`, {
      headers: getHeaders(token),
    });
  },

  sendFriendRequest: async (targetUserId, token) => {
    return fetch(`${API_BASE}/friends/request`, {
      method: "POST",
      headers: {
        ...getHeaders(token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ target_user_id: targetUserId }),
    });
  },
};
