import React from "react";
import { StyleSheet, Text, View, Image, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "../components/constants/theme";

export default function GalleryScreen({
  photos,
  handleSelectPhoto,
  handleLikePhoto,
}) {
  return (
    <View style={styles.galleryContainer}>
      <Text style={[styles.eyebrow, { fontFamily: "Oswald" }]}>
        YOU'RE IN THESE
      </Text>

      {photos.map((photo) => (
        <TouchableOpacity
          key={photo.id}
          style={styles.card}
          onPress={() => handleSelectPhoto(photo)}
        >
          <View style={styles.photoContainer}>
            <Image source={{ uri: photo.imageUrl }} style={styles.photoImage} />
            <View style={styles.photoOverlay} />

            {/* Top Bar on Image */}
            <View style={styles.cardHeader}>
              <View style={styles.glassBadge}>
                <Text style={styles.glassBadgeText}>
                  {photo.tagsCount} tagged
                </Text>
              </View>
              <TouchableOpacity
                style={styles.glassHeart}
                onPress={() => handleLikePhoto(photo.id)}
              >
                <Ionicons
                  name={photo.liked ? "heart" : "heart-outline"}
                  size={16}
                  color={COLORS.white}
                />
              </TouchableOpacity>
            </View>

            {/* Face Pins Overlay */}
            {photo.tags.map((tag) => (
              <View
                key={tag.id}
                style={[styles.facePin, { top: tag.y, left: tag.x }]}
              >
                <Text style={styles.facePinText}>{tag.initial}</Text>
              </View>
            ))}

            {/* Bottom Text Bar on Image */}
            <View style={styles.cardFooter}>
              <Text
                style={[styles.cardTitle, { fontFamily: "Fraunces-Italic" }]}
              >
                {photo.people}
              </Text>
              <Text style={[styles.cardSubtitle, { fontFamily: "Inter" }]}>
                {photo.meta}
              </Text>
            </View>
          </View>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  galleryContainer: {
    flex: 1,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.gray50,
    letterSpacing: 1.2,
    marginBottom: 12,
  },
  card: {
    borderRadius: 24,
    overflow: "hidden",
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.05)",
  },
  photoContainer: {
    width: "100%",
    height: 280,
    position: "relative",
  },
  photoImage: {
    width: "100%",
    height: "100%",
  },
  photoOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: COLORS.overlay,
  },
  cardHeader: {
    position: "absolute",
    top: 16,
    left: 16,
    right: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    zIndex: 2,
  },
  glassBadge: {
    backgroundColor: COLORS.glassStrong,
    borderRadius: 20,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
  },
  glassBadgeText: {
    color: COLORS.white,
    fontSize: 10.5,
    fontWeight: "600",
  },
  glassHeart: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.glassStrong,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
    justifyContent: "center",
    alignItems: "center",
  },
  facePin: {
    position: "absolute",
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: "rgba(0,0,0,0.35)",
    borderWidth: 1.5,
    borderColor: "rgba(255,255,255,0.6)",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 3,
  },
  facePinText: {
    color: COLORS.white,
    fontSize: 11,
    fontWeight: "700",
  },
  cardFooter: {
    position: "absolute",
    bottom: 16,
    left: 16,
    right: 16,
    zIndex: 2,
  },
  cardTitle: {
    color: COLORS.white,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 4,
  },
  cardSubtitle: {
    color: "rgba(255,255,255,0.7)",
    fontSize: 11.5,
  },
});
