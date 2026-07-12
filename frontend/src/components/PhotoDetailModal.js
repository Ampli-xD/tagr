import React from "react";
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  Image,
  ScrollView,
  Modal,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "./constants/theme";

export default function PhotoDetailModal({
  selectedPhoto,
  setSelectedPhoto,
  commentText,
  setCommentText,
  handlePostComment,
}) {
  return (
    <Modal
      visible={!!selectedPhoto}
      animationType="slide"
      transparent={true}
      onRequestClose={() => setSelectedPhoto(null)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          {/* Modal Header */}
          <View style={styles.modalHeader}>
            <TouchableOpacity
              onPress={() => setSelectedPhoto(null)}
              style={styles.modalCloseButton}
            >
              <Ionicons name="chevron-back" size={24} color={COLORS.white} />
            </TouchableOpacity>
            <Text style={[styles.modalTitle, { fontFamily: "Oswald" }]}>
              REVIEW TAGS
            </Text>
            <TouchableOpacity
              onPress={() => setSelectedPhoto(null)}
              style={styles.modalCloseButton}
            >
              <Ionicons name="checkmark" size={24} color={COLORS.white} />
            </TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={styles.modalScroll}>
            {selectedPhoto && (
              <>
                {/* Photo area with Tag overlays */}
                <View style={styles.modalPhotoContainer}>
                  <Image
                    source={{ uri: selectedPhoto.imageUrl }}
                    style={styles.modalPhotoImage}
                  />
                  <View style={styles.photoOverlay} />

                  {/* Face chip overlays */}
                  {selectedPhoto.tags &&
                    selectedPhoto.tags.map((tag) => (
                      <View
                        key={tag.id}
                        style={[styles.tagChip, { top: tag.y, left: tag.x }]}
                      >
                        <View style={styles.tagChipDot} />
                        <Text style={styles.tagChipText}>{tag.name}</Text>
                      </View>
                    ))}
                </View>

                {/* Confidences & tags list */}
                <View style={styles.tagsListSection}>
                  <Text
                    style={[
                      styles.eyebrow,
                      { fontFamily: "Oswald", marginBottom: 12 },
                    ]}
                  >
                    MATCHES
                  </Text>
                  {selectedPhoto.tags && selectedPhoto.tags.length > 0 ? (
                    selectedPhoto.tags.map((tag) => (
                      <View key={tag.id} style={styles.tagMatchRow}>
                        <View style={styles.avatarMini} />
                        <View style={{ flex: 1 }}>
                          <Text
                            style={[
                              styles.tagNameText,
                              { fontFamily: "Inter" },
                            ]}
                          >
                            {tag.name}
                          </Text>
                          <Text
                            style={[
                              styles.tagConfText,
                              { fontFamily: "Inter" },
                            ]}
                          >
                            {tag.confidence}% match
                          </Text>
                        </View>
                        <TouchableOpacity>
                          <Text style={styles.fixLink}>Fix</Text>
                        </TouchableOpacity>
                      </View>
                    ))
                  ) : (
                    <Text style={styles.noTagsText}>
                      No tags detected in this photo yet.
                    </Text>
                  )}
                </View>

                {/* Comments Section */}
                <View style={styles.commentsSection}>
                  <Text
                    style={[
                      styles.eyebrow,
                      { fontFamily: "Oswald", marginBottom: 12 },
                    ]}
                  >
                    COMMENTS
                  </Text>

                  {selectedPhoto.comments &&
                    selectedPhoto.comments.map((comment, index) => (
                      <View key={index} style={styles.commentItem}>
                        <Text style={styles.commentText}>
                          <Text
                            style={[
                              styles.commentAuthor,
                              { fontFamily: "Inter" },
                            ]}
                          >
                            {comment.author}:{" "}
                          </Text>
                          {comment.text}
                        </Text>
                      </View>
                    ))}

                  <View style={styles.commentInputRow}>
                    <TextInput
                      style={styles.commentInput}
                      placeholder="Write comment..."
                      placeholderTextColor={COLORS.gray50}
                      value={commentText}
                      onChangeText={setCommentText}
                    />
                    <TouchableOpacity
                      style={styles.commentPostButton}
                      onPress={handlePostComment}
                    >
                      <Text style={styles.commentPostText}>Post</Text>
                    </TouchableOpacity>
                  </View>
                </View>

                <TouchableOpacity
                  style={styles.button}
                  onPress={() => setSelectedPhoto(null)}
                >
                  <Text style={styles.buttonText}>Confirm tags</Text>
                </TouchableOpacity>
              </>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.95)",
  },
  modalContent: {
    flex: 1,
    marginTop: Platform.OS === "ios" ? 44 : 20,
  },
  modalHeader: {
    height: 60,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.05)",
  },
  modalCloseButton: {
    padding: 8,
  },
  modalTitle: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: "600",
    letterSpacing: 1,
  },
  modalScroll: {
    padding: 16,
    paddingBottom: 40,
  },
  modalPhotoContainer: {
    width: "100%",
    height: 300,
    borderRadius: 24,
    overflow: "hidden",
    position: "relative",
    marginBottom: 20,
  },
  modalPhotoImage: {
    width: "100%",
    height: "100%",
  },
  photoOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: COLORS.overlay,
  },
  tagChip: {
    position: "absolute",
    borderRadius: 20,
    paddingVertical: 7,
    paddingHorizontal: 13,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
    backgroundColor: "rgba(0,0,0,0.5)",
  },
  tagChipDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: COLORS.white,
  },
  tagChipText: {
    color: COLORS.white,
    fontSize: 11,
    fontWeight: "600",
  },
  tagsListSection: {
    marginBottom: 24,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.gray50,
    letterSpacing: 1.2,
  },
  tagMatchRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: COLORS.glass,
    borderWidth: 1,
    borderColor: COLORS.glassBorder,
    borderRadius: 18,
    padding: 12,
    marginBottom: 10,
  },
  avatarMini: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: COLORS.ink70,
    marginRight: 8,
  },
  tagNameText: {
    color: COLORS.white,
    fontSize: 13.5,
    fontWeight: "700",
  },
  tagConfText: {
    color: COLORS.gray50,
    fontSize: 10.5,
    marginTop: 2,
  },
  fixLink: {
    color: COLORS.white,
    fontSize: 11.5,
    fontWeight: "700",
    textDecorationLine: "underline",
  },
  noTagsText: {
    color: COLORS.gray50,
    fontSize: 13,
    fontStyle: "italic",
  },
  commentsSection: {
    marginBottom: 16,
  },
  commentItem: {
    marginBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.05)",
    paddingBottom: 6,
  },
  commentText: {
    color: COLORS.white,
    fontSize: 13,
    lineHeight: 18,
  },
  commentAuthor: {
    fontWeight: "700",
  },
  commentInputRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 12,
  },
  commentInput: {
    flex: 1,
    backgroundColor: "rgba(255,255,255,0.05)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)",
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: COLORS.white,
    fontSize: 13,
  },
  commentPostButton: {
    backgroundColor: COLORS.white,
    borderRadius: 12,
    paddingHorizontal: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  commentPostText: {
    color: COLORS.black,
    fontWeight: "700",
    fontSize: 13,
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
});
