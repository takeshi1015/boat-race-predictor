"""
Reinforcement Learner
Implements Q-learning for continuous improvement
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import numpy as np
import json

import config
from utils.logger import logger
from database.db_manager import get_db_manager


class ReinforcementLearner:
    """Q-learning based reinforcement learner"""
    
    def __init__(self):
        """Initialize reinforcement learner"""
        self.db_manager = get_db_manager()
        self.q_table = {}  # State -> {Action -> Q-value}
        self.alpha = config.Q_LEARNING_ALPHA
        self.gamma = config.Q_LEARNING_GAMMA
        self.epsilon = config.Q_LEARNING_EPSILON
    
    def get_state(self, race_data: Dict[str, Any]) -> str:
        """
        Get state representation from race data
        
        Args:
            race_data: Race information
            
        Returns:
            State string
        """
        # Discretize continuous values
        wind_speed = int(race_data.get("wind_speed", 0))
        water_surface = race_data.get("water_surface", "calm")
        temperature = int(race_data.get("temperature", 20) / 5) * 5
        
        return f"wind_{wind_speed}_water_{water_surface}_temp_{temperature}"
    
    def get_action(self, state: str, available_actions: List[str]) -> str:
        """
        Get action using epsilon-greedy policy
        
        Args:
            state: Current state
            available_actions: List of available actions
            
        Returns:
            Selected action
        """
        if np.random.random() < self.epsilon:
            # Explore
            return np.random.choice(available_actions)
        else:
            # Exploit
            if state not in self.q_table:
                self.q_table[state] = {action: 0.0 for action in available_actions}
            
            q_values = self.q_table[state]
            max_q = max(q_values.values())
            best_actions = [a for a, q in q_values.items() if q == max_q]
            return np.random.choice(best_actions)
    
    def learn(
        self,
        prediction: Dict[str, Any],
        result: Dict[str, Any]
    ) -> None:
        """
        Learn from prediction result using Q-learning
        
        Args:
            prediction: Prediction made
            result: Actual result
        """
        try:
            # Extract state and action
            state = self.get_state(prediction.get("race_data", {}))
            action = prediction.get("model", "ensemble")
            
            # Calculate reward
            reward = 1.0 if result.get("is_hit") else -1.0
            if result.get("is_hit"):
                reward *= result.get("actual_odds", 1.0) / 10.0  # Scale by odds
            
            # Initialize Q-table entry if needed
            if state not in self.q_table:
                self.q_table[state] = {action: 0.0}
            elif action not in self.q_table[state]:
                self.q_table[state][action] = 0.0
            
            # Q-learning update
            old_q = self.q_table[state][action]
            
            # Estimate next state value
            next_state = "terminal"
            if next_state in self.q_table:
                next_max_q = max(self.q_table[next_state].values())
            else:
                next_max_q = 0.0
            
            # Update Q-value
            new_q = old_q + self.alpha * (reward + self.gamma * next_max_q - old_q)
            self.q_table[state][action] = new_q
            
            logger.info(f"Q-learning update: state={state}, action={action}, reward={reward:.2f}, new_q={new_q:.4f}")
            
        except Exception as e:
            logger.error(f"Error in reinforcement learning: {e}")
    
    def save_q_table(self, filepath: str = "q_table.json") -> bool:
        """
        Save Q-table to file
        
        Args:
            filepath: Path to save Q-table
            
        Returns:
            True if saved successfully
        """
        try:
            # Convert to JSON-serializable format
            serializable_q_table = {}
            for state, actions in self.q_table.items():
                serializable_q_table[state] = {action: float(q) for action, q in actions.items()}
            
            with open(filepath, 'w') as f:
                json.dump(serializable_q_table, f, indent=2)
            
            logger.info(f"Q-table saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Q-table: {e}")
            return False
    
    def load_q_table(self, filepath: str = "q_table.json") -> bool:
        """
        Load Q-table from file
        
        Args:
            filepath: Path to load Q-table from
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(filepath, 'r') as f:
                self.q_table = json.load(f)
            
            logger.info(f"Q-table loaded from {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading Q-table: {e}")
            return False
    
    def get_policy(self) -> Dict[str, str]:
        """
        Get learned policy (best action for each state)
        
        Returns:
            Dictionary mapping states to best actions
        """
        policy = {}
        
        for state, actions in self.q_table.items():
            if actions:
                best_action = max(actions, key=actions.get)
                policy[state] = best_action
        
        return policy
