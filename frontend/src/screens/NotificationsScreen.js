import React from "react";
import { StyleSheet, Text, View, Image, TouchableOpacity } from "react-native";
import { COLORS } from "../components/constants/theme";

export default function NotificationsScreen({
  notifications,
  friendSuggestions,
  friendsList,
  sendFriendRequest,
}) {
  return (
    <View style={styles.notificationsContainer}>
      <Text style={[styles.eyebrow, { fontFamily: "Oswald" }]}>ALERTS</Text>
      {notifications.map((notif) => (
        <View key={notif.id} style={styles.notifItem}>
          <Image source={{ uri: notif.image }} style={styles.notifThumb} />
          <View style={styles.notifContent}>
            <Text style={styles.notifText}>{notif.text}</Text>
            <Text style={styles.notifTime}>{notif.time}</Text>
          </View>
          {notif.unread && <View style={styles.unreadDot} />}
        </View>
      ))}

      <Text style={[styles.eyebrow, { fontFamily: "Oswald", marginTop: 32 }]}>
        SUGGESTED FRIENDS
      </Text>
      {friendSuggestions.map((suggest) => (
        <View key={suggest.id} style={styles.friendItem}>
          <View>
            <Text style={styles.friendName}>{suggest.username}</Text>
            <Text style={styles.friendReason}>{suggest.matchReason}</Text>
          </View>
          <TouchableOpacity
            style={styles.smallButton}
            onPress={() => sendFriendRequest(suggest.id)}
          >
            <Text style={styles.smallButtonText}>Add</Text>
          </TouchableOpacity>
        </View>
      ))}

      <Text style={[styles.eyebrow, { fontFamily: "Oswald", marginTop: 32 }]}>
        MY CONNECTIONS
      </Text>
      <View style={styles.friendsListContainer}>
        {friendsList.map((friend) => (
          <View key={friend.id} style={styles.connectionItem}>
            <View style={styles.avatarMini} />
            <Text style={styles.connectionName}>{friend.username}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  notificationsContainer: {
    flex: 1,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.gray50,
    letterSpacing: 1.2,
    marginBottom: 12,
  },
  notifItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: COLORS.glass,
    borderRadius: 20,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
  },
  notifThumb: {
    width: 52,
    height: 52,
    borderRadius: 16,
    marginRight: 12,
  },
  notifContent: {
    flex: 1,
  },
  notifText: {
    fontFamily: "Inter",
    color: COLORS.white,
    fontSize: 12.5,
    lineHeight: 17,
  },
  notifTime: {
    fontFamily: "Inter",
    color: COLORS.gray50,
    fontSize: 10.5,
    marginTop: 4,
  },
  unreadDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: COLORS.white,
    marginLeft: 8,
  },
  friendItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: COLORS.glass,
    borderRadius: 20,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
  },
  friendName: {
    fontFamily: "Inter",
    color: COLORS.white,
    fontSize: 13.5,
    fontWeight: "700",
  },
  friendReason: {
    fontFamily: "Inter",
    color: COLORS.gray50,
    fontSize: 10.5,
    marginTop: 2,
  },
  smallButton: {
    backgroundColor: COLORS.white,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 100,
  },
  smallButtonText: {
    color: COLORS.black,
    fontSize: 11.5,
    fontWeight: "700",
  },
  friendsListContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  connectionItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: COLORS.glass,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
    borderRadius: 100,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  avatarMini: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: COLORS.ink70,
    marginRight: 8,
  },
  connectionName: {
    fontFamily: "Inter",
    color: COLORS.white,
    fontSize: 12,
    fontWeight: "600",
  },
});
