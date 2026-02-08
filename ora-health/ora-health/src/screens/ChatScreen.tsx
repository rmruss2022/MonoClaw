import React, { useState, useRef } from 'react';
import { 
  View, Text, StyleSheet, ScrollView, TextInput, 
  TouchableOpacity, KeyboardAvoidingView, Platform, ActivityIndicator 
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { theme } from '../theme';
import { Badge } from '../components/Badge';
import { chatAPI, ChatMessage } from '../services/api';

const SUGGESTED_PROMPTS = [
  "How can I manage stress better?",
  "I'm feeling overwhelmed today",
  "Help me practice gratitude",
  "I want to work on my goals",
];

export const ChatScreen: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentBehavior, setCurrentBehavior] = useState<string | null>(null);
  const scrollViewRef = useRef<ScrollView>(null);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setLoading(true);

    try {
      const aiResponse = await chatAPI.sendMessage(text, messages);
      setMessages(prev => [...prev, aiResponse]);
      if (aiResponse.behavior) {
        setCurrentBehavior(aiResponse.behavior);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: "I'm having trouble connecting right now. Please try again.",
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
      setTimeout(() => {
        scrollViewRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  };

  const handlePromptPress = (prompt: string) => {
    sendMessage(prompt);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
        keyboardVerticalOffset={0}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>Your Space</Text>
            {currentBehavior && (
              <View style={styles.behaviorContainer}>
                <View style={styles.behaviorDot} />
                <Text style={styles.behaviorText}>{currentBehavior}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Messages */}
        <ScrollView 
          ref={scrollViewRef}
          style={styles.messages}
          contentContainerStyle={styles.messagesContent}
          showsVerticalScrollIndicator={false}
        >
          {messages.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyEmoji}>💜</Text>
              <Text style={styles.emptyTitle}>I'm here to listen and support you</Text>
              <Text style={styles.emptySubtitle}>
                Share what's on your mind, or try one of these:
              </Text>
              
              <View style={styles.prompts}>
                {SUGGESTED_PROMPTS.map((prompt, index) => (
                  <TouchableOpacity
                    key={index}
                    style={styles.prompt}
                    onPress={() => handlePromptPress(prompt)}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.promptText}>{prompt}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ) : (
            messages.map((message, index) => (
              <View
                key={index}
                style={[
                  styles.messageBubble,
                  message.role === 'user' ? styles.userBubble : styles.aiBubble
                ]}
              >
                <Text style={[
                  styles.messageText,
                  message.role === 'user' ? styles.userText : styles.aiText
                ]}>
                  {message.content}
                </Text>
                
                {message.behavior && (
                  <Badge 
                    label={message.behavior} 
                    color={theme.colors.sage} 
                    size="small"
                    style={styles.messageBehavior}
                  />
                )}
              </View>
            ))
          )}
          
          {loading && (
            <View style={styles.loadingBubble}>
              <ActivityIndicator size="small" color={theme.colors.sage} />
            </View>
          )}
        </ScrollView>

        {/* Input */}
        <View style={styles.inputContainer}>
          <View style={styles.inputWrapper}>
            <TextInput
              style={styles.input}
              value={inputText}
              onChangeText={setInputText}
              placeholder="Share what's on your mind..."
              placeholderTextColor={theme.colors.textLight}
              multiline
              maxLength={500}
              editable={!loading}
            />
            <TouchableOpacity 
              style={[styles.sendButton, (!inputText.trim() || loading) && styles.sendButtonDisabled]}
              onPress={() => sendMessage(inputText)}
              disabled={!inputText.trim() || loading}
            >
              <Text style={styles.sendButtonText}>↑</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.warmCream,
  },
  keyboardView: {
    flex: 1,
  },
  
  // Header
  header: {
    padding: theme.spacing.base,
    paddingTop: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderLight,
    backgroundColor: theme.colors.warmWhite,
  },
  title: {
    fontSize: theme.typography.fontSize.hero,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.text,
  },
  behaviorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: theme.spacing.xs,
  },
  behaviorDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: theme.colors.sage,
    marginRight: theme.spacing.xs,
  },
  behaviorText: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textSecondary,
    fontWeight: theme.typography.fontWeight.medium,
  },
  
  // Messages
  messages: {
    flex: 1,
  },
  messagesContent: {
    padding: theme.spacing.base,
  },
  
  // Empty State
  empty: {
    paddingTop: theme.spacing.xxxl,
    alignItems: 'center',
  },
  emptyEmoji: {
    fontSize: 64,
    marginBottom: theme.spacing.lg,
  },
  emptyTitle: {
    fontSize: theme.typography.fontSize.headingLarge,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
    textAlign: 'center',
    marginBottom: theme.spacing.sm,
  },
  emptySubtitle: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
    textAlign: 'center',
    marginBottom: theme.spacing.xl,
  },
  
  // Prompts
  prompts: {
    width: '100%',
    gap: theme.spacing.sm,
  },
  prompt: {
    backgroundColor: theme.colors.cardBg,
    padding: theme.spacing.base,
    borderRadius: theme.borderRadius.md,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    ...theme.shadows.small,
  },
  promptText: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.text,
    textAlign: 'center',
  },
  
  // Message Bubbles
  messageBubble: {
    maxWidth: '80%',
    padding: theme.spacing.base,
    borderRadius: theme.borderRadius.lg,
    marginBottom: theme.spacing.md,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: theme.colors.sage,
    borderBottomRightRadius: theme.borderRadius.xs,
  },
  aiBubble: {
    alignSelf: 'flex-start',
    backgroundColor: theme.colors.cardBg,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    borderBottomLeftRadius: theme.borderRadius.xs,
  },
  messageText: {
    fontSize: theme.typography.fontSize.body,
    lineHeight: 22,
  },
  userText: {
    color: theme.colors.warmWhite,
  },
  aiText: {
    color: theme.colors.text,
  },
  messageBehavior: {
    marginTop: theme.spacing.sm,
  },
  
  // Loading
  loadingBubble: {
    alignSelf: 'flex-start',
    backgroundColor: theme.colors.cardBg,
    padding: theme.spacing.base,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    marginBottom: theme.spacing.md,
  },
  
  // Input
  inputContainer: {
    padding: theme.spacing.base,
    backgroundColor: theme.colors.warmWhite,
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderLight,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.xxl,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: theme.spacing.base,
    paddingVertical: theme.spacing.sm,
  },
  input: {
    flex: 1,
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.text,
    maxHeight: 100,
    paddingTop: theme.spacing.xs,
  },
  sendButton: {
    width: 32,
    height: 32,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.sage,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: theme.spacing.sm,
  },
  sendButtonDisabled: {
    backgroundColor: theme.colors.borderLight,
    opacity: 0.5,
  },
  sendButtonText: {
    fontSize: 20,
    color: theme.colors.warmWhite,
    fontWeight: theme.typography.fontWeight.bold,
  },
});
