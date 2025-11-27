# spam_checker.py
import re
import pandas as pd
import numpy as np
from datetime import datetime
import hashlib
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class EmailSpamChecker:
    """
    Standalone Spam Checker Class for Keddy Mailer
    Use: from spam_checker import EmailSpamChecker
    """
    
    def __init__(self):
        self.spam_patterns = self._initialize_patterns()
        self.analysis_history = []
        
    def _initialize_patterns(self):
        """Advanced spam patterns initialization"""
        return {
            # 🔥 HIGH RISK PATTERNS (Weight: 3)
            'high_risk': {
                'financial_scam': [
                    r'\b(loan|credit|money|cash|earn|profit|investment|rich|crore|lakh|rupee)\b',
                    r'\b(double your|quick rich|get rich|make money|earn daily|income source)\b',
                    r'\b(work from home|online earning|passive income|financial freedom)\b'
                ],
                'urgency_fear': [
                    r'\b(urgent|immediately|now|hurry|last chance|limited time|expiring)\b',
                    r'\b(final notice|last attempt|closing soon|don\'t miss|hurry up)\b',
                    r'\b(act now|instant|quick|fast|immediate|right away)\b'
                ],
                'winner_lottery': [
                    r'\b(won|winner|prize|lottery|jackpot|selected|congratulations)\b',
                    r'\b(you have won|you are winner|lucky winner|prize winner)\b',
                    r'\b(congrats|congratulation|you won|you\'ve won)\b'
                ]
            },
            
            # ⚠️ MEDIUM RISK PATTERNS (Weight: 2)
            'medium_risk': {
                'free_offers': [
                    r'\b(free|no cost|zero charges|complimentary|bonus|gift)\b',
                    r'\b(100% free|absolutely free|totally free|completely free)\b',
                    r'\b(no fees|no charge|without cost|free of cost)\b'
                ],
                'verification_requests': [
                    r'\b(verify|update|password|account|security|click here)\b',
                    r'\b(confirm|validate|authenticate|authorize|secure your)\b',
                    r'\b(account suspended|login required|password reset)\b'
                ],
                'health_products': [
                    r'\b(weight loss|fat burn|medicine|pill|cure|treatment)\b',
                    r'\b(burn fat|lose weight|slimming|diet pill|weight reduce)\b',
                    r'\b(health supplement|body shape|fitness|muscle building)\b'
                ]
            },
            
            # 📧 LOW RISK PATTERNS (Weight: 1)
            'low_risk': {
                'marketing': [
                    r'\b(offer|deal|discount|sale|bargain|cheap|save)\b',
                    r'\b(special price|limited offer|exclusive deal|best price)\b',
                    r'\b(buy now|order now|shop now|purchase|get it now)\b'
                ],
                'suspicious_words': [
                    r'\b(amazing|incredible|miracle|secret|hidden|confidential)\b',
                    r'\b(guaranteed|proven|scientific|doctor approved|clinical)\b',
                    r'\b(risk-free|money back|satisfaction guaranteed|refund)\b'
                ]
            }
        }
    
    def _extract_features(self, text):
        """Advanced feature extraction from text"""
        if not text:
            return {}
        
        text_lower = text.lower()
        features = {}
        
        # Pattern matching with weights
        total_score = 0
        found_patterns = []
        
        for risk_level, categories in self.spam_patterns.items():
            weight = {'high_risk': 3, 'medium_risk': 2, 'low_risk': 1}[risk_level]
            
            for category, patterns in categories.items():
                for pattern in patterns:
                    matches = re.findall(pattern, text_lower)
                    if matches:
                        pattern_score = len(matches) * weight
                        total_score += pattern_score
                        found_patterns.append({
                            'category': category,
                            'pattern': pattern,
                            'matches': matches,
                            'score': pattern_score
                        })
        
        # Text-based features
        features['text_length'] = len(text)
        features['uppercase_ratio'] = sum(1 for c in text if c.isupper()) / max(1, len(text))
        features['exclamation_count'] = text.count('!')
        features['question_count'] = text.count('?')
        features['url_count'] = len(re.findall(r'http[s]?://[^\s]+', text))
        features['number_count'] = len(re.findall(r'\d+', text))
        features['spam_keyword_count'] = total_score
        features['found_patterns'] = found_patterns
        
        return features
    
    def check_spam_score(self, email_body, email_subject=""):
        """
        Main function to check spam score for email body
        Parameters:
        - email_body: string (required)
        - email_subject: string (optional)
        
        Returns: Comprehensive spam analysis report
        """
        # Probability calculation
        spam_probability, details = self._calculate_spam_probability(email_subject, email_body)
        
        # Decision logic
        if spam_probability >= 80:
            spam_level = "HIGH_RISK"
            is_spam = True
            risk_color = "danger"
        elif spam_probability >= 60:
            spam_level = "MEDIUM_RISK"
            is_spam = True
            risk_color = "warning"
        elif spam_probability >= 40:
            spam_level = "LOW_RISK"
            is_spam = False
            risk_color = "info"
        else:
            spam_level = "SAFE"
            is_spam = False
            risk_color = "success"
        
        # Generate detailed report
        report = {
            'is_spam': is_spam,
            'spam_level': spam_level,
            'risk_color': risk_color,
            'spam_probability': round(spam_probability, 2),
            'risk_breakdown': {
                'base_score': details['base_score'],
                'risk_factors': details['risk_factors'],
                'total_risk': details['base_score'] + details['risk_factors']
            },
            'detected_patterns': {
                'subject': details['subject_features'].get('found_patterns', []),
                'body': details['body_features'].get('found_patterns', [])
            },
            'text_analysis': {
                'subject_length': details['subject_features'].get('text_length', 0),
                'body_length': details['body_features'].get('text_length', 0),
                'uppercase_ratio': details['subject_features'].get('uppercase_ratio', 0),
                'urls_found': details['body_features'].get('url_count', 0),
                'exclamation_count': details['subject_features'].get('exclamation_count', 0)
            },
            'timestamp': datetime.now().isoformat(),
            'email_hash': hashlib.md5(f"{email_subject}{email_body}".encode()).hexdigest()
        }
        
        # Save to history
        self.analysis_history.append(report)
        
        return report
    
    def _calculate_spam_probability(self, subject, body):
        """Advanced spam probability calculation"""
        subject_features = self._extract_features(subject)
        body_features = self._extract_features(body)
        
        # Base scoring
        base_score = (
            subject_features.get('spam_keyword_count', 0) * 1.5 +  # Subject gets more weight
            body_features.get('spam_keyword_count', 0)
        )
        
        # Additional risk factors
        risk_factors = 0
        
        # UPPERCASE words in subject
        if subject_features.get('uppercase_ratio', 0) > 0.3:
            risk_factors += 20
        
        # Too many exclamations
        if subject_features.get('exclamation_count', 0) >= 3:
            risk_factors += 15
        
        # URLs in body
        if body_features.get('url_count', 0) >= 2:
            risk_factors += 25
        
        # Short body with high spam score
        if body_features.get('text_length', 0) < 100 and base_score > 5:
            risk_factors += 20
        
        # Number-heavy content
        if body_features.get('number_count', 0) >= 5:
            risk_factors += 10
        
        total_risk = base_score + risk_factors
        
        # Convert to probability (0-100%)
        probability = min(100, max(0, total_risk))
        
        return probability, {
            'base_score': base_score,
            'risk_factors': risk_factors,
            'subject_features': subject_features,
            'body_features': body_features
        }
    
    def get_detailed_analysis(self, email_body, email_subject=""):
        """
        Get detailed analysis with suggestions
        """
        basic_report = self.check_spam_score(email_body, email_subject)
        
        # Add suggestions
        suggestions = self._generate_suggestions(basic_report)
        basic_report['suggestions'] = suggestions
        
        return basic_report
    
    def _generate_suggestions(self, report):
        """Generate improvement suggestions based on analysis"""
        suggestions = []
        
        if report['spam_probability'] > 60:
            suggestions.append("🚨 High spam risk detected! Consider revising the content.")
        
        if report['text_analysis']['uppercase_ratio'] > 0.3:
            suggestions.append("🔠 Avoid using too many uppercase letters in subject.")
        
        if report['text_analysis']['exclamation_count'] >= 3:
            suggestions.append("❗ Reduce exclamation marks in subject line.")
        
        if report['text_analysis']['urls_found'] >= 2:
            suggestions.append("🔗 Too many URLs detected. Consider reducing links.")
        
        if report['text_analysis']['body_length'] < 100:
            suggestions.append("📝 Email body seems too short. Add more meaningful content.")
        
        # Pattern-specific suggestions
        body_patterns = report['detected_patterns']['body']
        for pattern in body_patterns:
            if pattern['category'] == 'financial_scam':
                suggestions.append("💰 Avoid financial scam related keywords")
            elif pattern['category'] == 'urgency_fear':
                suggestions.append("⏰ Reduce urgency-creating language")
            elif pattern['category'] == 'winner_lottery':
                suggestions.append("🎯 Remove lottery/winner related terms")
        
        if not suggestions:
            suggestions.append("✅ Content looks clean and professional!")
        
        return suggestions

# Quick utility function
def quick_spam_check(email_body, email_subject=""):
    """
    Quick spam check function
    Usage: from spam_checker import quick_spam_check
    """
    checker = EmailSpamChecker()
    return checker.check_spam_score(email_body, email_subject)