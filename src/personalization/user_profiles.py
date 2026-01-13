"""
User Personalization System - Adapts to user communication patterns
"""

import json
import os
import time

class UserPersonalization:
    def __init__(self, personalization_file="analytics/personalization.json"):
        self.personalization_file = personalization_file
        self.user_profiles = {}
        self.load_profiles()

    def load_profiles(self):
        """Load user profiles from file"""
        try:
            if os.path.exists(self.personalization_file):
                with open(self.personalization_file, 'r', encoding='utf-8') as f:
                    self.user_profiles = json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading user profiles: {e}")
            self.user_profiles = {}

    def save_profiles(self):
        """Save user profiles to file"""
        try:
            os.makedirs(os.path.dirname(self.personalization_file), exist_ok=True)
            with open(self.personalization_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving user profiles: {e}")

    def update_profile(self, user_id, message, response=None):
        """Update user profile based on interaction"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'total_messages': 0,
                'language': 'ru',
                'topics': {},
                'style': 'formal',
                'last_active': time.time(),
                'preferred_format': 'detailed',  # concise/detailed/technical
                'response_length': 'normal'  # short/normal/long
            }

        profile = self.user_profiles[user_id]
        profile['total_messages'] += 1
        profile['last_active'] = time.time()

        # Detect language
        self._detect_language(profile, message)

        # Analyze topics
        self._analyze_topics(profile, message)

        # Analyze communication style
        self._analyze_style(profile, message)

        # Analyze preferred response format
        self._analyze_response_preferences(profile, message, response)

        self.save_profiles()
        return profile

    def _detect_language(self, profile, message):
        """Detect user language"""
        try:
            # Simple language detection based on Cyrillic characters
            cyrillic_chars = sum(1 for c in message if ord(c) > 127 and c.isalpha())
            total_chars = sum(1 for c in message if c.isalpha())

            if total_chars > 0:
                cyrillic_ratio = cyrillic_chars / total_chars
                if cyrillic_ratio > 0.5:
                    profile['language'] = 'ru'
                else:
                    profile['language'] = 'en'
        except:
            pass

    def _analyze_topics(self, profile, message):
        """Analyze user interests/topics"""
        message_lower = message.lower()

        topic_keywords = {
            'telephony': ['ватс', 'телефон', 'sip', 'бизнес-телефон', 'pbx', 'телефония'],
            'internet': ['интернет', 'подключение', 'тариф', 'скорость', 'wifi'],
            'billing': ['счет', 'оплата', 'тариф', 'эсф', 'авр', 'платеж'],
            'technical': ['настройка', 'конфигурация', 'оборудование', 'техподдержка'],
            'mobile': ['мобильная', 'сим', 'gsm', 'lte', '4g', '5g'],
            'security': ['безопасность', 'защита', 'vpn', 'шифрование']
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                profile['topics'][topic] = profile['topics'].get(topic, 0) + 1

    def _analyze_style(self, profile, message):
        """Analyze user communication style"""
        message_lower = message.lower()

        if any(word in message_lower for word in ['плиз', 'пожалуйста', 'спасибо', 'извините', 'please', 'thank']):
            profile['style'] = 'polite'
        elif any(word in message_lower for word in ['быстрее', 'срочно', 'немедленно', 'urgent', 'asap']):
            profile['style'] = 'urgent'
        elif len(message.split()) > 20:
            profile['style'] = 'detailed'
        elif len(message.split()) < 5:
            profile['style'] = 'concise'

    def _analyze_response_preferences(self, profile, message, response=None):
        """Analyze preferred response format"""
        if not response:
            return

        # Analyze based on question type
        if any(word in message.lower() for word in ['кратко', 'коротко', 'brief', 'short']):
            profile['preferred_format'] = 'concise'
        elif any(word in message.lower() for word in ['подробно', 'детально', 'detailed']):
            profile['preferred_format'] = 'detailed'
        elif any(word in message.lower() for word in ['технически', 'technical', 'specs']):
            profile['preferred_format'] = 'technical'

        # Analyze response length preference
        if len(response) < 200:
            profile['response_length'] = 'short'
        elif len(response) > 1000:
            profile['response_length'] = 'long'
        else:
            profile['response_length'] = 'normal'

    def get_personalized_greeting(self, user_id):
        """Get personalized greeting based on user profile"""
        if user_id not in self.user_profiles:
            return "Здравствуйте!"

        profile = self.user_profiles[user_id]

        # Language-based greeting
        if profile.get('language') == 'en':
            return "Hello!"
        elif profile.get('language') == 'kk':
            return "Сәлеметсіз бе!"

        # Style-based greeting
        style = profile.get('style', 'formal')
        if style == 'polite':
            return "Здравствуйте! Чем могу помочь?"
        elif style == 'urgent':
            return "Здравствуйте! Я готов помочь быстро."
        else:
            return "Здравствуйте!"

    def get_user_insights(self, user_id):
        """Get insights about user behavior"""
        if user_id not in self.user_profiles:
            return None

        profile = self.user_profiles[user_id]

        # Find top topics
        top_topics = sorted(profile.get('topics', {}).items(), key=lambda x: x[1], reverse=True)[:3]
        top_topics = [topic for topic, count in top_topics if count > 0]

        return {
            'language': profile.get('language', 'ru'),
            'style': profile.get('style', 'formal'),
            'top_topics': top_topics,
            'preferred_format': profile.get('preferred_format', 'detailed'),
            'total_messages': profile.get('total_messages', 0)
        }

# Global instance
personalization = UserPersonalization()
