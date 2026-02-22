import json
import os
import random
import logging
import asyncio
import re
import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8474641060:AAH4cRqRcBFhvEaQowd0jG8WQtPDTffzN0w"
ADMIN_ID = 6539341659
DATABASE_FILE = "casino_data.json"
PROMO_FILE = "promo_codes.json"
SHOP_FILE = "shop_items.json"
INVENTORY_FILE = "inventory.json"
COUNTERS_FILE = "counters.json"
STATUS_SHOP_FILE = "status_shop.json"
BANK_DATA_FILE = "bank_data.json"
BANK_SETTINGS_FILE = "bank_settings.json"

START_BALANCE = 10000  # Стартовый баланс: 10к

logging.basicConfig(level=logging.INFO)

# === СОСТОЯНИЯ ===
class TransferStates(StatesGroup):
    select_item = State()
    enter_username = State()
    confirm = State()

class BankStates(StatesGroup):
    waiting_deposit_amount = State()
    waiting_deposit_days = State()
    waiting_loan_amount = State()
    waiting_loan_days = State()
    waiting_card_amount = State()
    waiting_loan_payment = State()

# === БАЗА ДАННЫХ ===
class Database:
    def __init__(self, file):
        self.file = file
        self._ensure()
    
    def _ensure(self):
        """Создает файл, если его нет"""
        if not os.path.exists(self.file):
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def read(self):
        """Читает данные из файла"""
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def write(self, data):
        """Записывает данные в файл"""
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# === СЧЕТЧИКИ ===
class CountersDB:
    def __init__(self):
        self.db = Database(COUNTERS_FILE)
    
    def get_next_number(self, item_id):
        """Получить следующий глобальный номер для предмета"""
        data = self.db.read()
        if 'item_counters' not in data:
            data['item_counters'] = {}
        
        current = data['item_counters'].get(item_id, 0)
        next_num = current + 1
        data['item_counters'][item_id] = next_num
        self.db.write(data)
        return next_num
    
    def get_all_counters(self):
        """Получить все счетчики"""
        data = self.db.read()
        return data.get('item_counters', {})

# === ПОЛЬЗОВАТЕЛИ ===
class UserDB:
    def __init__(self):
        self.db = Database(DATABASE_FILE)
    
    def get(self, user_id):
        """Получить данные пользователя, создать если нет"""
        data = self.db.read()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            # Создаем нового пользователя с статусом Новичок
            data[user_id_str] = {
                'balance': START_BALANCE,
                'games_played': 0,
                'wins': 0,
                'used_promocodes': [],
                'status': 'novice',
                'last_bonus': None,
                'bonus_history': []
            }
            self.db.write(data)
            return data[user_id_str]
        
        # Проверяем наличие всех ключей у существующего пользователя
        user = data[user_id_str]
        changed = False
        
        if 'balance' not in user:
            user['balance'] = START_BALANCE
            changed = True
        if 'games_played' not in user:
            user['games_played'] = 0
            changed = True
        if 'wins' not in user:
            user['wins'] = 0
            changed = True
        if 'used_promocodes' not in user:
            user['used_promocodes'] = []
            changed = True
        if 'status' not in user:
            user['status'] = 'novice'
            changed = True
        if 'last_bonus' not in user:
            user['last_bonus'] = None
            changed = True
        if 'bonus_history' not in user:
            user['bonus_history'] = []
            changed = True
        
        if changed:
            self.db.write(data)
        
        return user
    
    def update(self, user_id, **kwargs):
        """Обновить данные пользователя"""
        data = self.db.read()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = self.get(user_id)
        
        for k, v in kwargs.items():
            data[user_id_str][k] = v
        
        self.db.write(data)
    
    def top_by_balance(self, limit=10):
        """Получить топ игроков по балансу (без админа)"""
        data = self.db.read()
        users = []
        for uid, u in data.items():
            if uid == str(ADMIN_ID):
                continue
            if 'balance' not in u:
                u['balance'] = 0
            users.append((uid, u))
        
        users.sort(key=lambda x: x[1].get('balance', 0), reverse=True)
        return users[:limit]
    
    def top_by_status(self):
        """Получить топ игроков по статусам"""
        data = self.db.read()
        status_groups = {}
        
        for uid, u in data.items():
            if uid == str(ADMIN_ID):
                continue
            status = u.get('status', 'novice')
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append((uid, u))
        
        # Сортируем каждую группу по балансу
        for status in status_groups:
            status_groups[status].sort(key=lambda x: x[1].get('balance', 0), reverse=True)
        
        return status_groups
    
    def all_users(self):
        """Вернуть список всех ID пользователей"""
        return [int(uid) for uid in self.db.read().keys()]
    
    def get_all_users_data(self):
        """Вернуть все данные пользователей (для админа)"""
        return self.db.read()

# === МАГАЗИН СТАТУСОВ ===
class StatusShopDB:
    def __init__(self):
        self.db = Database(STATUS_SHOP_FILE)
        self._ensure_defaults()
    
    def _ensure_defaults(self):
        """Создает статусы по умолчанию, если их нет"""
        data = self.db.read()
        if not data:
            data = {
                "novice": {
                    "name": "Новичок",
                    "emoji": "🌱",
                    "price": 0,
                    "min_bonus": 500,
                    "max_bonus": 2500,
                    "description": "Начальный статус для всех новичков"
                },
                "player": {
                    "name": "Игрок",
                    "emoji": "🎮",
                    "price": 50000,
                    "min_bonus": 2500,
                    "max_bonus": 10000,
                    "description": "Уже кое-что понимаешь в играх"
                },
                "gambler": {
                    "name": "Азартный",
                    "emoji": "🎲",
                    "price": 250000,
                    "min_bonus": 10000,
                    "max_bonus": 50000,
                    "description": "Риск — твоё второе имя"
                },
                "vip": {
                    "name": "VIP",
                    "emoji": "💎",
                    "price": 1000000,
                    "min_bonus": 50000,
                    "max_bonus": 250000,
                    "description": "Особый статус для особых игроков"
                },
                "legend": {
                    "name": "Легенда",
                    "emoji": "👑",
                    "price": 5000000,
                    "min_bonus": 250000,
                    "max_bonus": 1000000,
                    "description": "Легенда казино, сам Бог удачи"
                },
                "oligarch": {
                    "name": "Олигарх",
                    "emoji": "💰",
                    "price": 25000000,
                    "min_bonus": 1000000,
                    "max_bonus": 5000000,
                    "description": "У тебя больше денег, чем у некоторых стран"
                },
                "immortal": {
                    "name": "Бессмертный",
                    "emoji": "⚡",
                    "price": 100000000,
                    "min_bonus": 5000000,
                    "max_bonus": 25000000,
                    "description": "Ты достиг просветления"
                }
            }
            self.db.write(data)
    
    def get_all_statuses(self):
        """Получить все статусы"""
        return self.db.read()
    
    def get_status(self, status_id):
        """Получить конкретный статус"""
        data = self.db.read()
        return data.get(status_id)
    
    def buy_status(self, user_id, status_id, user_db):
        """Купить статус"""
        statuses = self.db.read()
        if status_id not in statuses:
            return {'ok': False, 'msg': '❌ Статус не найден!'}
        
        status = statuses[status_id]
        user = user_db.get(user_id)
        
        if user['status'] == status_id:
            return {'ok': False, 'msg': '❌ У вас уже есть этот статус!'}
        
        if user['balance'] < status['price']:
            return {'ok': False, 'msg': f'❌ Недостаточно средств! Нужно: {self.fmt(status["price"])}'}
        
        # Списываем деньги
        new_balance = user['balance'] - status['price']
        user_db.update(user_id, balance=new_balance, status=status_id)
        
        return {
            'ok': True,
            'msg': f'✅ Вы купили статус {status["emoji"]} {status["name"]}!',
            'status': status
        }
    
    def fmt(self, n):
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}ккк"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}кк"
        if n >= 1000:
            return f"{n/1000:.1f}к"
        return str(n)

# === ПРОМОКОДЫ ===
class PromoDB:
    def __init__(self):
        self.db = Database(PROMO_FILE)
    
    def create(self, code, reward, limit=100, days=30):
        """Создать новый промокод"""
        promos = self.db.read()
        if code in promos:
            return False
        
        promos[code] = {
            'reward': reward,
            'limit': limit,
            'used': 0,
            'expires': (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(),
            'users': []
        }
        self.db.write(promos)
        return True
    
    def use(self, code, user_id, user_db):
        """Использовать промокод"""
        promos = self.db.read()
        if code not in promos:
            return {'ok': False, 'msg': '❌ Промокод не найден!'}
        
        p = promos[code]
        
        # Проверяем наличие всех ключей
        if 'expires' not in p:
            return {'ok': False, 'msg': '❌ Ошибка в промокоде!'}
        if 'limit' not in p:
            p['limit'] = 100
        if 'used' not in p:
            p['used'] = 0
        if 'users' not in p:
            p['users'] = []
        
        if datetime.datetime.now() > datetime.datetime.fromisoformat(p['expires']):
            return {'ok': False, 'msg': '❌ Промокод просрочен!'}
        if p['used'] >= p['limit']:
            return {'ok': False, 'msg': '❌ Лимит использований!'}
        if user_id in p['users']:
            return {'ok': False, 'msg': '❌ Вы уже использовали!'}
        
        user = user_db.get(user_id)
        new_balance = user['balance'] + p['reward']
        user['used_promocodes'].append(code)
        user_db.update(user_id, balance=new_balance, used_promocodes=user['used_promocodes'])
        
        p['used'] += 1
        p['users'].append(user_id)
        self.db.write(promos)
        
        return {'ok': True, 'msg': f'🎉 Получено: {self.fmt(p["reward"])}'}
    
    def all(self):
        """Получить все промокоды"""
        promos = self.db.read()
        # Проверяем каждый промокод
        for code, p in promos.items():
            if 'expires' not in p:
                p['expires'] = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
            if 'limit' not in p:
                p['limit'] = 100
            if 'used' not in p:
                p['used'] = 0
            if 'users' not in p:
                p['users'] = []
        return promos
    
    def fmt(self, n):
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}ккк"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}кк"
        if n >= 1000:
            return f"{n/1000:.1f}к"
        return str(n)

# === МАГАЗИН NFT ===
class ShopDB:
    def __init__(self):
        self.shop = Database(SHOP_FILE)
        self.inv = Database(INVENTORY_FILE)
        self.counters = CountersDB()
    
    def add(self, id, name, price, quantity, description="", emoji="🎁"):
        """Добавить товар в магазин"""
        items = self.shop.read()
        if id in items:
            return False
        
        items[id] = {
            'name': name, 
            'price': price, 
            'quantity': quantity,
            'sold': 0,
            'description': description,
            'emoji': emoji
        }
        self.shop.write(items)
        return True
    
    def buy(self, id, user_id, user_db):
        """Купить товар"""
        items = self.shop.read()
        inv = self.inv.read()
        
        if id not in items:
            return {'ok': False, 'msg': '❌ Товар не найден!'}
        
        item = items[id]
        user = user_db.get(user_id)
        
        if item['quantity'] <= 0:
            return {'ok': False, 'msg': '❌ Нет в наличии!'}
        if user['balance'] < item['price']:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        # Получаем следующий глобальный номер для этого типа NFT
        global_number = self.counters.get_next_number(id)
        
        new_balance = user['balance'] - item['price']
        user_db.update(user_id, balance=new_balance)
        
        item['quantity'] -= 1
        item['sold'] += 1
        self.shop.write(items)
        
        user_inv = inv.get(str(user_id), [])
        user_inv.append({
            'item_id': id,
            'global_number': global_number,
            'name': item['name'],
            'emoji': item['emoji'],
            'description': item['description'],
            'purchased_at': datetime.datetime.now().isoformat(),
            'unique_id': f"{user_id}_{id}_{global_number}_{random.randint(1000, 9999)}"
        })
        inv[str(user_id)] = user_inv
        self.inv.write(inv)
        
        return {
            'ok': True, 
            'msg': f'🎉 Куплено {item["emoji"]} {item["name"]} #{global_number}',
            'number': global_number
        }
    
    def items(self):
        """Получить все товары"""
        items = self.shop.read()
        # Проверяем каждый товар
        for id, item in items.items():
            if 'quantity' not in item:
                item['quantity'] = 0
            if 'sold' not in item:
                item['sold'] = 0
            if 'description' not in item:
                item['description'] = ''
            if 'emoji' not in item:
                item['emoji'] = '🎁'
        return items
    
    def inventory(self, user_id):
        """Получить инвентарь пользователя"""
        inv = self.inv.read()
        user_inv = inv.get(str(user_id), [])
        return user_inv
    
    def get_item_by_unique_id(self, unique_id):
        """Найти предмет по unique_id во всех инвентарях"""
        inv = self.inv.read()
        for user_id, items in inv.items():
            for item in items:
                if item.get('unique_id') == unique_id:
                    return item, int(user_id)
        return None, None
    
    def remove_from_inventory(self, user_id, unique_id):
        """Удалить предмет из инвентаря"""
        inv = self.inv.read()
        if str(user_id) in inv:
            inv[str(user_id)] = [i for i in inv[str(user_id)] if i.get('unique_id') != unique_id]
            self.inv.write(inv)
            return True
        return False
    
    def add_to_inventory(self, user_id, item_data):
        """Добавить предмет в инвентарь"""
        inv = self.inv.read()
        if str(user_id) not in inv:
            inv[str(user_id)] = []
        inv[str(user_id)].append(item_data)
        self.inv.write(inv)
    
    def debug_inventory(self, user_id):
        """Отладочный метод для проверки инвентаря"""
        inv = self.inv.read()
        user_inv = inv.get(str(user_id), [])
        print(f"DEBUG: User {user_id} has {len(user_inv)} items in inventory")
        for item in user_inv:
            print(f"  - #{item.get('global_number')} {item.get('name')} ({item.get('unique_id')})")
        return user_inv

# === ИГРЫ ===
class Games:
    def __init__(self, db):
        self.db = db
    
    def can(self, user_id, amount):
        user = self.db.get(user_id)
        return user['balance'] >= amount
    
    def coin(self, user_id, bet, choice):
        if not self.can(user_id, bet):
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        user = self.db.get(user_id)
        
        # Сначала списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Затем играем
        result = random.choice(['орел', 'решка'])
        win = choice == result
        
        if win:
            win_amount = bet * 2
            final_balance = new_balance + win_amount
            self.db.update(user_id, 
                          balance=final_balance, 
                          games_played=user.get('games_played', 0) + 1, 
                          wins=user.get('wins', 0) + 1)
            return {'ok': True, 'win': True, 'res': result, 'amount': win_amount, 'balance': final_balance}
        else:
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            return {'ok': True, 'win': False, 'res': result, 'amount': bet, 'balance': new_balance}
    
    def slots(self, user_id, bet):
        if not self.can(user_id, bet):
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        user = self.db.get(user_id)
        
        # Сначала списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Затем играем
        symbols = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
        reels = [random.choice(symbols) for _ in range(3)]
        
        if reels[0] == reels[1] == reels[2]:
            mult = 10 if reels[0] == '7️⃣' else 5
            win = bet * mult
            final_balance = new_balance + win
            self.db.update(user_id, 
                          balance=final_balance, 
                          games_played=user.get('games_played', 0) + 1, 
                          wins=user.get('wins', 0) + 1)
            return {'ok': True, 'win': True, 'reels': reels, 'mult': mult, 'amount': win, 'balance': final_balance}
        else:
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            return {'ok': True, 'win': False, 'reels': reels, 'amount': bet, 'balance': new_balance}
    
    def dice(self, user_id, bet, pred):
        if not self.can(user_id, bet):
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        if pred < 1 or pred > 6:
            return {'ok': False, 'msg': '❌ Число от 1 до 6!'}
        
        user = self.db.get(user_id)
        
        # Сначала списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Затем играем
        roll = random.randint(1, 6)
        win = pred == roll
        
        if win:
            win_amount = bet * 6
            final_balance = new_balance + win_amount
            self.db.update(user_id, 
                          balance=final_balance, 
                          games_played=user.get('games_played', 0) + 1, 
                          wins=user.get('wins', 0) + 1)
            return {'ok': True, 'win': True, 'roll': roll, 'amount': win_amount, 'balance': final_balance}
        else:
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            return {'ok': True, 'win': False, 'roll': roll, 'amount': bet, 'balance': new_balance}

# === ИГРА КРАШ ===
class CrashGame:
    def __init__(self, db):
        self.db = db
        self.active_games = {}  # user_id -> game_data
    
    def start(self, user_id, bet, target_x):
        """Начать игру Краш"""
        # Если есть активная игра, но она уже завершена - удаляем
        if user_id in self.active_games:
            if self.active_games[user_id].get('status') in ['won', 'lost']:
                del self.active_games[user_id]
            else:
                return {'ok': False, 'msg': '❌ У вас уже есть активная игра! Завершите её.'}
        
        user = self.db.get(user_id)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        if target_x < 1.1:
            return {'ok': False, 'msg': '❌ Минимальный множитель: 1.1x'}
        
        if target_x > 100:
            return {'ok': False, 'msg': '❌ Максимальный множитель: 100x'}
        
        # Списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Генерируем случайный множитель
        crash_point = self._generate_crash_point()
        
        game_data = {
            'user_id': user_id,
            'bet': bet,
            'target_x': target_x,
            'crash_point': crash_point,
            'status': 'active'
        }
        
        self.active_games[user_id] = game_data
        
        # Определяем результат
        if crash_point >= target_x:
            # Выигрыш
            win_amount = int(bet * target_x)
            final_balance = new_balance + win_amount
            self.db.update(user_id, 
                          balance=final_balance,
                          games_played=user.get('games_played', 0) + 1,
                          wins=user.get('wins', 0) + 1)
            game_data['status'] = 'won'
            game_data['win_amount'] = win_amount
            game_data['final_balance'] = final_balance
        else:
            # Проигрыш
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            game_data['status'] = 'lost'
            game_data['final_balance'] = new_balance
        
        # Удаляем игру после завершения
        if game_data['status'] in ['won', 'lost']:
            del self.active_games[user_id]
        
        return {
            'ok': True,
            'game_data': game_data
        }
    
    def _generate_crash_point(self):
        """Генерирует случайную точку краша"""
        r = random.random()
        crash = 1.0 / (1.0 - r * 0.95)
        return round(crash, 2)

# === МИНЫ ===
# === МИНЫ С ПРАВИЛЬНЫМИ МНОЖИТЕЛЯМИ ===
# === МИНЫ С ПРАВИЛЬНЫМИ МНОЖИТЕЛЯМИ ===
class Mines:
    def __init__(self, db):
        self.db = db
        self.games = {}
    
    def get_multipliers(self, mines_count):
        """
        УНИКАЛЬНЫЕ множители для КАЖДОГО количества мин от 1 до 24
        """
        multipliers = {}
        
        for cells in range(1, 25):
            if mines_count == 1:
                # 1 мина - x5 на 24 клетке
                mult = 1 + (cells * 0.06)
                mult = min(mult, 5.0)
                
            elif mines_count == 2:
                # 2 мины - x10 на 24 клетке
                mult = 1 + (cells * 0.17)
                mult = min(mult, 10.0)
                
            elif mines_count == 3:
                # 3 мины - x15 на 24 клетке
                mult = 1 + (cells * 0.38)
                mult = min(mult, 15.0)
                
            elif mines_count == 4:
                # 4 мины - x20 на 24 клетке
                mult = 1 + (cells * 0.49)
                mult = min(mult, 20.0)
                
            elif mines_count == 5:
                # 5 мин - x25 на 24 клетке
                mult = 1 + (cells * 0.60)
                mult = min(mult, 25.0)
                
            elif mines_count == 6:
                # 6 мин - x30 на 24 клетке
                mult = 1 + (cells * 0.81)
                mult = min(mult, 30.0)
                
            elif mines_count == 7:
                # 7 мин - x40 на 24 клетке
                mult = 1 + (cells * 1.0)
                mult = min(mult, 40.0)
                
            elif mines_count == 8:
                # 8 мин - x50 на 24 клетке
                mult = 1 + (cells * 1.14)
                mult = min(mult, 50.0)
                
            elif mines_count == 9:
                # 9 мин - x60 на 24 клетке
                mult = 1 + (cells * 1.36)
                mult = min(mult, 60.0)
                
            elif mines_count == 10:
                # 10 мин - x70 на 24 клетке
                mult = 1 + (cells * 1.68)
                mult = min(mult, 70.0)
                
            elif mines_count == 11:
                # 11 мин - x80 на 24 клетке
                mult = 1 + (cells * 1.89)
                mult = min(mult, 80.0)
                
            elif mines_count == 12:
                # 12 мин - x90 на 24 клетке
                mult = 1 + (cells * 3.0)
                mult = min(mult, 90.0)
                
            elif mines_count == 13:
                # 13 мин - x100 на 24 клетке
                mult = 1 + (cells * 3.03)
                mult = min(mult, 100.0)
                
            elif mines_count == 14:
                # 14 мин - x110 на 24 клетке
                mult = 1 + (cells * 3.34)
                mult = min(mult, 110.0)
                
            elif mines_count == 15:
                # 15 мин - x120 на 24 клетке
                mult = 1 + (cells * 3.66)
                mult = min(mult, 120.0)
                
            elif mines_count == 16:
                # 16 мин - x130 на 24 клетке
                mult = 1 + (cells * 3.88)
                mult = min(mult, 130.0)
                
            elif mines_count == 17:
                # 17 мин - x140 на 24 клетке
                mult = 1 + (cells * 4.09)
                mult = min(mult, 140.0)
                
            elif mines_count == 18:
                # 18 мин - x150 на 24 клетке
                mult = 1 + (cells * 4.11)
                mult = min(mult, 150.0)
                
            elif mines_count == 19:
                # 19 мин - x160 на 24 клетке
                mult = 1 + (cells * 4.43)
                mult = min(mult, 160.0)
                
            elif mines_count == 20:
                # 20 мин - x170 на 24 клетке
                mult = 1 + (cells * 4.64)
                mult = min(mult, 170.0)
                
            elif mines_count == 21:
                # 21 мина - x180 на 24 клетке
                mult = 1 + (cells * 4.86)
                mult = min(mult, 180.0)
                
            elif mines_count == 22:
                # 22 мины - x190 на 24 клетке
                mult = 1 + (cells * 8.08)
                mult = min(mult, 190.0)
                
            elif mines_count == 23:
                # 23 мины - x200 на 24 клетке
                mult = 1 + (cells * 8.19)
                mult = min(mult, 200.0)
                
            elif mines_count == 24:
                # 24 мины - x250 на 24 клетке
                mult = 1 + (cells * 8.48)
                mult = min(mult, 250.0)
            else:
                # Для других значений
                mult = 1 + (cells * (mines_count * 0.15))
                mult = min(mult, mines_count * 10)
            
            multipliers[cells] = round(mult, 2)
        
        return multipliers
    
    def start(self, user_id, bet, mines=3):
        """Начать игру в мины"""
        if user_id in self.games:
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её.'}
        
        user = self.db.get(user_id)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        # Сразу списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Создаем поле 5x5
        field = [['⬜' for _ in range(5)] for _ in range(5)]
        
        # Расставляем мины
        mines_positions = []
        while len(mines_positions) < mines:
            pos = (random.randint(0, 4), random.randint(0, 4))
            if pos not in mines_positions:
                mines_positions.append(pos)
        
        self.games[user_id] = {
            'bet': bet, 
            'field': field, 
            'mines': mines_positions, 
            'count': mines,
            'opened': [], 
            'mult': 1.0, 
            'mults': self.get_multipliers(mines), 
            'won': 0,
            'current_balance': new_balance
        }
        
        return {'ok': True, 'data': self.games[user_id]}
    
    def open(self, user_id, row, col):
        """Открыть клетку"""
        if user_id not in self.games:
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[user_id]
        pos = (row, col)
        
        if pos in g['opened']:
            return {'ok': False, 'msg': '❌ Уже открыто!'}
        
        # Проверяем, не мина ли это
        if pos in g['mines']:
            # Проигрыш - показываем все мины
            for r, c in g['mines']:
                g['field'][r][c] = '💣'
            g['field'][row][col] = '💥'
            opened = len(g['opened'])
            
            # Обновляем статистику
            user = self.db.get(user_id)
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            
            del self.games[user_id]
            return {'ok': True, 'over': True, 'field': g['field'], 'opened': opened, 'bet': g['bet']}
        
        # Безопасная клетка
        g['opened'].append(pos)
        g['field'][row][col] = '🟩'
        opened = len(g['opened'])
        g['mult'] = g['mults'].get(opened, 2.5)
        g['won'] = int(g['bet'] * g['mult'])
        
        max_cells = 25 - g['count']
        
        return {
            'ok': True, 
            'over': False, 
            'field': g['field'],
            'opened': opened, 
            'mult': g['mult'], 
            'won': g['won'],
            'max': max_cells
        }
    
    def cashout(self, user_id):
        """Забрать выигрыш"""
        if user_id not in self.games:
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[user_id]
        
        # Проверяем, что открыта хотя бы 1 клетка
        if len(g['opened']) == 0:
            return {'ok': False, 'msg': '❌ Нельзя забрать, не открыв ни одной клетки! Сначала откройте клетку.'}
        
        # Начисляем выигрыш
        user = self.db.get(user_id)
        new_balance = g['current_balance'] + g['won']
        self.db.update(user_id, balance=new_balance, 
                      games_played=user.get('games_played', 0) + 1,
                      wins=user.get('wins', 0) + 1)
        
        # Показываем все мины
        for r, c in g['mines']:
            g['field'][r][c] = '💣'
        
        opened = len(g['opened'])
        mult = g['mult']
        bet = g['bet']
        won = g['won']
        field = [row[:] for row in g['field']]
        
        del self.games[user_id]
        return {
            'ok': True, 
            'won': won, 
            'balance': new_balance,
            'field': field, 
            'opened': opened, 
            'mult': mult, 
            'bet': bet
        }
    
    def kb(self, user_id, field, active=True):
        """Создать клавиатуру для игры"""
        kb = []
        for i in range(5):
            row = []
            for j in range(5):
                if field[i][j] in ['🟩', '💣', '💥']:
                    row.append(InlineKeyboardButton(text=field[i][j], callback_data="ignore"))
                else:
                    emoji = "🟦" if active else "⬛"
                    row.append(InlineKeyboardButton(text=emoji, callback_data=f"mines_{user_id}_{i}_{j}"))
            kb.append(row)
        
        if active:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"cashout_{user_id}")])
        
        kb.append([InlineKeyboardButton(text="🎮 Новая", callback_data="mines_new")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)
    
# === НОВАЯ ИГРА БАШНЯ ===
class TowerGame:
    def __init__(self, db):
        self.db = db
        self.games = {}  # user_id -> game_data
        self.multipliers = [1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0]
    
    def start(self, user_id, bet, mines_per_row=1):
        """Начать игру Башня"""
        if user_id in self.games:
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её.'}
        
        if mines_per_row < 1 or mines_per_row > 4:
            return {'ok': False, 'msg': '❌ Количество мин должно быть от 1 до 4!'}
        
        user = self.db.get(user_id)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        # Сразу списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Создаем первый ряд
        row = self._generate_row(mines_per_row)
        
        game_data = {
            'user_id': user_id,
            'bet': bet,
            'mines_per_row': mines_per_row,
            'current_row': 0,
            'max_rows': 9,
            'rows': [row],  # все ряды хранятся здесь
            'opened_cells': [],  # какие клетки открыты в каждом ряду
            'current_multiplier': 1.0,
            'current_balance': new_balance,
            'won': 0,
            'game_over': False
        }
        
        self.games[user_id] = game_data
        return {'ok': True, 'data': game_data}
    
    def _generate_row(self, mines_count):
        """Генерирует ряд с минами"""
        cells = ['⬜'] * 5
        mine_positions = []
        while len(mine_positions) < mines_count:
            pos = random.randint(0, 4)
            if pos not in mine_positions:
                mine_positions.append(pos)
        return {'cells': cells, 'mines': mine_positions, 'revealed': False}
    
    def open_cell(self, user_id, row_idx, col):
        """Открыть клетку в башне"""
        if user_id not in self.games:
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[user_id]
        
        if g['game_over']:
            return {'ok': False, 'msg': '❌ Игра уже завершена!'}
        
        # Проверяем, что это текущий ряд
        if row_idx != g['current_row']:
            return {'ok': False, 'msg': '❌ Можно открывать только текущий ряд!'}
        
        # Проверяем, что в этом ряду еще не открывали клетку
        row_opened = [c for c in g['opened_cells'] if c.startswith(f"{row_idx}_")]
        if len(row_opened) > 0:
            return {'ok': False, 'msg': '❌ В этом ряду уже открыта клетка!'}
        
        # Проверяем, что клетка в пределах ряда
        if col < 0 or col > 4:
            return {'ok': False, 'msg': '❌ Неверная клетка!'}
        
        row = g['rows'][row_idx]
        
        # Проверяем, мина ли это
        if col in row['mines']:
            # Проигрыш - показываем все мины в этом ряду
            for c in range(5):
                if c in row['mines']:
                    row['cells'][c] = '💣'
            row['cells'][col] = '💥'
            row['revealed'] = True
            
            # Обновляем статистику
            user = self.db.get(user_id)
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            
            g['game_over'] = True
            result = {
                'ok': True, 
                'over': True, 
                'mine': True, 
                'row': row_idx, 
                'col': col,
                'row_data': row,
                'bet': g['bet']
            }
            
            del self.games[user_id]
            return result
        
        # Открываем клетку (безопасно)
        g['opened_cells'].append(f"{row_idx}_{col}")
        row['cells'][col] = '🟩'
        row['revealed'] = True
        
        # Рассчитываем текущий выигрыш
        g['current_multiplier'] = self.multipliers[row_idx]
        g['won'] = int(g['bet'] * g['current_multiplier'])
        
        # Проверяем, достигли ли максимума
        if row_idx >= g['max_rows'] - 1:
            # Автоматический выигрыш на последнем ряду
            return self._auto_win(user_id)
        
        # Переходим на следующий ряд, но текущий ряд остается видимым
        g['current_row'] += 1
        
        # Генерируем новый ряд, если его еще нет
        if len(g['rows']) <= g['current_row']:
            new_row = self._generate_row(g['mines_per_row'])
            g['rows'].append(new_row)
        
        return {
            'ok': True, 
            'over': False, 
            'row': row_idx, 
            'col': col,
            'next_row': g['current_row'],
            'multiplier': g['current_multiplier'],
            'won': g['won']
        }
    
    def _auto_win(self, user_id):
        """Автоматический выигрыш при достижении максимума"""
        if user_id not in self.games:
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[user_id]
        
        # Начисляем выигрыш
        user = self.db.get(user_id)
        new_balance = g['current_balance'] + g['won']
        self.db.update(user_id, balance=new_balance, 
                      games_played=user.get('games_played', 0) + 1,
                      wins=user.get('wins', 0) + 1)
        
        won = g['won']
        multiplier = g['current_multiplier']
        rows_completed = g['current_row'] + 1
        
        result = {
            'ok': True,
            'over': True,
            'win': True,
            'won': won,
            'multiplier': multiplier,
            'rows': rows_completed,
            'balance': new_balance
        }
        
        del self.games[user_id]
        return result
    
    def cashout(self, user_id):
        """Забрать выигрыш досрочно"""
        if user_id not in self.games:
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[user_id]
        
        if g['game_over']:
            return {'ok': False, 'msg': '❌ Игра уже завершена!'}
        
        # Проверяем, что открыта хотя бы 1 клетка
        if len(g['opened_cells']) == 0:
            return {'ok': False, 'msg': '❌ Нельзя забрать, не открыв ни одной клетки! Сначала откройте клетку.'}
        
        # Начисляем выигрыш
        user = self.db.get(user_id)
        new_balance = g['current_balance'] + g['won']
        self.db.update(user_id, balance=new_balance, 
                      games_played=user.get('games_played', 0) + 1,
                      wins=user.get('wins', 0) + 1)
        
        won = g['won']
        multiplier = g['current_multiplier']
        rows_completed = g['current_row']  # текущий ряд (уже перешли на следующий)
        
        result = {
            'ok': True,
            'won': won,
            'multiplier': multiplier,
            'rows': rows_completed,
            'balance': new_balance
        }
        
        del self.games[user_id]
        return result
    
    def create_keyboard(self, user_id, game_data):
        """Создает клавиатуру для башни с сохранением всех рядов"""
        kb = []
        
        # Показываем все ряды сверху вниз (от первого к последнему)
        for r_idx in range(len(game_data['rows'])):
            row = game_data['rows'][r_idx]
            row_buttons = []
            
            # Определяем, какой это ряд (текущий, пройденный или будущий)
            if r_idx < game_data['current_row']:
                # Уже пройденный ряд - показываем результат
                for c in range(5):
                    cell_key = f"{r_idx}_{c}"
                    if cell_key in game_data['opened_cells']:
                        # Открытая клетка
                        row_buttons.append(InlineKeyboardButton(text="🟩", callback_data="ignore"))
                    elif c in row['mines']:
                        # Мина (но мы её не показываем, пока не проиграли)
                        row_buttons.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
                    else:
                        # Остальные клетки
                        row_buttons.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            
            elif r_idx == game_data['current_row']:
                # Текущий ряд - показываем закрытые клетки для выбора
                for c in range(5):
                    row_buttons.append(InlineKeyboardButton(
                        text="🟦", 
                        callback_data=f"tower_open_{user_id}_{r_idx}_{c}"
                    ))
            
            else:
                # Будущие ряды - пока не видны
                for c in range(5):
                    row_buttons.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            
            kb.append(row_buttons)
        
        # Добавляем кнопку для забора выигрыша, если есть открытые клетки
        if len(game_data['opened_cells']) > 0 and not game_data['game_over']:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"tower_cashout_{user_id}")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)

# === ИГРА РУЛЕТКА ===
class RouletteGame:
    def __init__(self, db):
        self.db = db
        
        # Цвета чисел
        self.red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        self.black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        
        # Множители для разных типов ставок
        self.multipliers = {
            'even': 2,           # чётное
            'odd': 2,            # нечётное
            'red': 2,            # красное
            'black': 2,          # чёрное
            '1-12': 3,           # первая дюжина
            '13-24': 3,          # вторая дюжина
            '25-36': 3,          # третья дюжина
            'dozen1': 3,         # первая дюжина
            'dozen2': 3,         # вторая дюжина
            'dozen3': 3,         # третья дюжина
            'column1': 3,        # первая колонка
            'column2': 3,        # вторая колонка
            'column3': 3,        # третья колонка
            'zero': 36,          # зеро
            'number': 36         # конкретное число
        }
    
    def play(self, user_id, bet, bet_type, bet_value=None):
        """Сыграть в рулетку"""
        user = self.db.get(user_id)
        if user['balance'] < bet:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        # Сначала списываем ставку
        new_balance = user['balance'] - bet
        self.db.update(user_id, balance=new_balance)
        
        # Генерируем результат
        number = random.randint(0, 36)
        color = 'green' if number == 0 else ('red' if number in self.red_numbers else 'black')
        
        # Определяем выигрыш
        win = False
        multiplier = 0
        
        if bet_type == 'even' and number != 0 and number % 2 == 0:
            win = True
            multiplier = self.multipliers['even']
        elif bet_type == 'odd' and number != 0 and number % 2 == 1:
            win = True
            multiplier = self.multipliers['odd']
        elif bet_type == 'red' and color == 'red':
            win = True
            multiplier = self.multipliers['red']
        elif bet_type == 'black' and color == 'black':
            win = True
            multiplier = self.multipliers['black']
        elif bet_type == '1-12' and 1 <= number <= 12:
            win = True
            multiplier = self.multipliers['1-12']
        elif bet_type == '13-24' and 13 <= number <= 24:
            win = True
            multiplier = self.multipliers['13-24']
        elif bet_type == '25-36' and 25 <= number <= 36:
            win = True
            multiplier = self.multipliers['25-36']
        elif bet_type == 'dozen1' and 1 <= number <= 12:
            win = True
            multiplier = self.multipliers['dozen1']
        elif bet_type == 'dozen2' and 13 <= number <= 24:
            win = True
            multiplier = self.multipliers['dozen2']
        elif bet_type == 'dozen3' and 25 <= number <= 36:
            win = True
            multiplier = self.multipliers['dozen3']
        elif bet_type == 'column1' and number % 3 == 1 and number != 0:
            win = True
            multiplier = self.multipliers['column1']
        elif bet_type == 'column2' and number % 3 == 2 and number != 0:
            win = True
            multiplier = self.multipliers['column2']
        elif bet_type == 'column3' and number % 3 == 0 and number != 0:
            win = True
            multiplier = self.multipliers['column3']
        elif bet_type == 'zero' and number == 0:
            win = True
            multiplier = self.multipliers['zero']
        elif bet_type == 'number' and bet_value is not None and number == bet_value:
            win = True
            multiplier = self.multipliers['number']
        
        if win:
            win_amount = bet * multiplier
            final_balance = new_balance + win_amount
            self.db.update(user_id, balance=final_balance,
                          games_played=user.get('games_played', 0) + 1,
                          wins=user.get('wins', 0) + 1)
            return {
                'ok': True,
                'win': True,
                'number': number,
                'color': color,
                'amount': win_amount,
                'multiplier': multiplier,
                'balance': final_balance
            }
        else:
            self.db.update(user_id, 
                          games_played=user.get('games_played', 0) + 1)
            return {
                'ok': True,
                'win': False,
                'number': number,
                'color': color,
                'amount': bet,
                'balance': new_balance
            }

# === НОВЫЙ КЛАСС БАНКА ===
class BankDB:
    def __init__(self):
        self.db = Database(BANK_DATA_FILE)
        self.settings = Database(BANK_SETTINGS_FILE)
        self._ensure_settings()
    
    def _ensure_settings(self):
        """Создает настройки банка по умолчанию"""
        settings = self.settings.read()
        if not settings:
            settings = {
                "deposit_rates": {
                    "7": 3.0,
                    "14": 4.5,
                    "30": 6.0,
                    "90": 8.0,
                    "180": 10.0,
                    "365": 12.0
                },
                "loan_rates": {
                    "7": 5.0,
                    "14": 7.0,
                    "30": 10.0,
                    "90": 12.0,
                    "180": 15.0,
                    "365": 20.0
                },
                "max_loan_amount": 1000000,
                "min_credit_score": 300
            }
            self.settings.write(settings)
    
    def get_user_bank(self, user_id):
        """Получить банковские данные пользователя"""
        data = self.db.read()
        user_str = str(user_id)
        
        if user_str not in data:
            data[user_str] = {
                'card_balance': 0,
                'deposits': [],
                'loans': [],
                'credit_history': 500  # начальный кредитный рейтинг
            }
            self.db.write(data)
        
        return data[user_str]
    
    def update_user_bank(self, user_id, **kwargs):
        """Обновить банковские данные"""
        data = self.db.read()
        user_str = str(user_id)
        
        if user_str not in data:
            data[user_str] = self.get_user_bank(user_id)
        
        for k, v in kwargs.items():
            data[user_str][k] = v
        
        self.db.write(data)
    
    def card_deposit(self, user_id, amount, main_balance):
        """Положить деньги на карту (скрытый баланс)"""
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        if main_balance < amount:
            return {'ok': False, 'msg': '❌ Недостаточно средств на основном счете!'}
        
        user_bank = self.get_user_bank(user_id)
        new_card = user_bank['card_balance'] + amount
        
        self.update_user_bank(user_id, card_balance=new_card)
        
        return {
            'ok': True, 
            'msg': f'✅ На карту зачислено: {bot_core.fmt(amount)}\n'
                   f'💳 Баланс карты: {bot_core.fmt(new_card)}'
        }
    
    def card_withdraw(self, user_id, amount, main_balance):
        """Снять деньги с карты"""
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        
        user_bank = self.get_user_bank(user_id)
        if user_bank['card_balance'] < amount:
            return {'ok': False, 'msg': '❌ Недостаточно средств на карте!'}
        
        new_card = user_bank['card_balance'] - amount
        new_main = main_balance + amount
        
        self.update_user_bank(user_id, card_balance=new_card)
        
        return {
            'ok': True, 
            'msg': f'✅ С карты снято: {bot_core.fmt(amount)}\n'
                   f'💳 Новый баланс карты: {bot_core.fmt(new_card)}\n'
                   f'💰 Основной баланс: {bot_core.fmt(new_main)}'
        }
    
    def create_deposit(self, user_id, amount, days, main_balance):
        """Создать вклад"""
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        if main_balance < amount:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        settings = self.settings.read()
        rates = settings['deposit_rates']
        
        days_str = str(days)
        if days_str not in rates:
            return {'ok': False, 'msg': '❌ Доступные сроки: 7, 14, 30, 90, 180, 365 дней'}
        
        rate = rates[days_str]
        
        user_bank = self.get_user_bank(user_id)
        
        # Создаем вклад
        deposit_id = f"dep_{user_id}_{len(user_bank['deposits'])}_{random.randint(100,999)}"
        end_date = datetime.datetime.now() + datetime.timedelta(days=days)
        
        deposit = {
            'id': deposit_id,
            'amount': amount,
            'days': days,
            'rate': rate,
            'start_date': datetime.datetime.now().isoformat(),
            'end_date': end_date.isoformat(),
            'status': 'active'
        }
        
        user_bank['deposits'].append(deposit)
        self.update_user_bank(user_id, deposits=user_bank['deposits'])
        
        return {
            'ok': True,
            'msg': f'🏦 **Вклад создан!**\n\n'
                   f'💰 Сумма: {bot_core.fmt(amount)}\n'
                   f'📅 Срок: {days} дней\n'
                   f'📈 Ставка: {rate}%\n'
                   f'💵 Доход: {bot_core.fmt(int(amount * rate / 100))}\n'
                   f'📆 Выплата: {end_date.strftime("%d.%m.%Y")}'
        }
    
    def close_deposit(self, user_id, deposit_id):
        """Закрыть вклад досрочно (без процентов)"""
        user_bank = self.get_user_bank(user_id)
        
        for i, dep in enumerate(user_bank['deposits']):
            if dep['id'] == deposit_id and dep['status'] == 'active':
                # Возвращаем только тело вклада
                amount = dep['amount']
                dep['status'] = 'closed_early'
                user_bank['deposits'][i] = dep
                self.update_user_bank(user_id, deposits=user_bank['deposits'])
                
                return {
                    'ok': True,
                    'amount': amount,
                    'msg': f'✅ Вклад закрыт досрочно. Возвращено: {bot_core.fmt(amount)} (без процентов)'
                }
        
        return {'ok': False, 'msg': '❌ Вклад не найден!'}
    
    def process_deposits(self, user_id):
        """Обработать созревшие вклады"""
        user_bank = self.get_user_bank(user_id)
        now = datetime.datetime.now()
        total_return = 0
        
        for i, dep in enumerate(user_bank['deposits']):
            if dep['status'] == 'active':
                end_date = datetime.datetime.fromisoformat(dep['end_date'])
                if now >= end_date:
                    # Вклад созрел
                    profit = int(dep['amount'] * dep['rate'] / 100)
                    total_return += dep['amount'] + profit
                    dep['status'] = 'completed'
                    user_bank['deposits'][i] = dep
        
        if total_return > 0:
            self.update_user_bank(user_id, deposits=user_bank['deposits'])
            user_bank['card_balance'] += total_return
            self.update_user_bank(user_id, card_balance=user_bank['card_balance'])
        
        return total_return
    
    def create_loan(self, user_id, amount, days, main_balance):
        """Взять кредит"""
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        
        settings = self.settings.read()
        rates = settings['loan_rates']
        
        days_str = str(days)
        if days_str not in rates:
            return {'ok': False, 'msg': '❌ Доступные сроки: 7, 14, 30, 90, 180, 365 дней'}
        
        if amount > settings['max_loan_amount']:
            return {'ok': False, 'msg': f'❌ Максимальная сумма кредита: {bot_core.fmt(settings["max_loan_amount"])}'}
        
        user_bank = self.get_user_bank(user_id)
        
        # Проверка кредитной истории
        if user_bank['credit_history'] < settings['min_credit_score']:
            return {'ok': False, 'msg': f'❌ Кредитная история слишком низкая ({user_bank["credit_history"]})'}
        
        rate = rates[days_str]
        total_to_return = int(amount * (1 + rate / 100))
        daily_payment = total_to_return // days
        
        loan_id = f"loan_{user_id}_{len(user_bank['loans'])}_{random.randint(100,999)}"
        end_date = datetime.datetime.now() + datetime.timedelta(days=days)
        
        loan = {
            'id': loan_id,
            'amount': amount,
            'days': days,
            'rate': rate,
            'total_to_return': total_to_return,
            'remaining': total_to_return,
            'daily_payment': daily_payment,
            'start_date': datetime.datetime.now().isoformat(),
            'end_date': end_date.isoformat(),
            'status': 'active'
        }
        
        user_bank['loans'].append(loan)
        self.update_user_bank(user_id, loans=user_bank['loans'])
        
        return {
            'ok': True,
            'msg': f'🏦 **Кредит одобрен!**\n\n'
                   f'💰 Сумма: {bot_core.fmt(amount)}\n'
                   f'📅 Срок: {days} дней\n'
                   f'📈 Ставка: {rate}%\n'
                   f'💵 К возврату: {bot_core.fmt(total_to_return)}\n'
                   f'📆 Ежедневный платеж: {bot_core.fmt(daily_payment)}\n'
                   f'⚠️ Не забывайте вовремя платить!'
        }
    
    def pay_loan(self, user_id, loan_id, amount, main_balance):
        """Оплатить кредит"""
        if amount <= 0:
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        if main_balance < amount:
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        user_bank = self.get_user_bank(user_id)
        
        for i, loan in enumerate(user_bank['loans']):
            if loan['id'] == loan_id and loan['status'] == 'active':
                if amount > loan['remaining']:
                    amount = loan['remaining']
                
                loan['remaining'] -= amount
                
                if loan['remaining'] <= 0:
                    loan['status'] = 'paid'
                    # Улучшаем кредитную историю
                    user_bank['credit_history'] = min(1000, user_bank['credit_history'] + 50)
                
                user_bank['loans'][i] = loan
                self.update_user_bank(user_id, loans=user_bank['loans'], credit_history=user_bank['credit_history'])
                
                return {
                    'ok': True,
                    'msg': f'✅ Оплачено: {bot_core.fmt(amount)}\n'
                           f'📊 Осталось: {bot_core.fmt(loan["remaining"])}'
                }
        
        return {'ok': False, 'msg': '❌ Кредит не найден!'}
    
    def process_loans(self, user_id):
        """Обработать просрочки по кредитам"""
        user_bank = self.get_user_bank(user_id)
        now = datetime.datetime.now()
        
        for i, loan in enumerate(user_bank['loans']):
            if loan['status'] == 'active':
                end_date = datetime.datetime.fromisoformat(loan['end_date'])
                if now > end_date and loan['remaining'] > 0:
                    # Просрочка - штраф и ухудшение кредитной истории
                    penalty = int(loan['remaining'] * 0.1)  # 10% штраф
                    loan['remaining'] += penalty
                    user_bank['credit_history'] = max(0, user_bank['credit_history'] - 100)
                    loan['status'] = 'overdue'
                    user_bank['loans'][i] = loan
        
        self.update_user_bank(user_id, loans=user_bank['loans'], credit_history=user_bank['credit_history'])

    def get_bank_menu(self, user_id):
        """Получить главное меню банка"""
        user_bank = self.get_user_bank(user_id)
        
        # Обрабатываем созревшие вклады
        deposits_return = self.process_deposits(user_id)
        self.process_loans(user_id)
        
        # Считаем активные вклады
        active_deposits = [d for d in user_bank['deposits'] if d['status'] == 'active']
        active_loans = [l for l in user_bank['loans'] if l['status'] == 'active']
        
        total_deposits = sum(d['amount'] for d in active_deposits)
        total_loans = sum(l['remaining'] for l in active_loans)
        
        text = f"🏦 **БАНК**\n\n"
        text += f"💳 Баланс карты: {bot_core.fmt(user_bank['card_balance'])}\n"
        text += f"📊 Кредитный рейтинг: {user_bank['credit_history']}/1000\n\n"
        text += f"💰 Активные вклады: {len(active_deposits)} на {bot_core.fmt(total_deposits)}\n"
        text += f"💸 Активные кредиты: {len(active_loans)} на {bot_core.fmt(total_loans)}"
        
        return text

# === ОСНОВНОЙ БОТ ===
class BotCore:
    def __init__(self):
        self.db = UserDB()
        self.promo = PromoDB()
        self.shop = ShopDB()
        self.status_shop = StatusShopDB()
        self.bank = BankDB()
        self.games = Games(self.db)
        self.crash = CrashGame(self.db)
        self.mines = Mines(self.db)
        self.tower = TowerGame(self.db)
        self.roulette = RouletteGame(self.db)
        self.counters = CountersDB()
    
    def parse_bet(self, text, user_balance=None):
        """
        Парсит ставку с поддержкой:
        - числа: 1000
        - суффиксы: 1к, 2.5кк, 3ккк
        - ключевое слово "все" - весь баланс
        """
        if not text:
            return 0
        
        text = str(text).lower().strip()
        
        # Обработка "все" - весь баланс
        if text == 'все' and user_balance is not None:
            return user_balance
        
        # Обработка чисел с суффиксами
        match = re.match(r'^(\d+(?:\.\d+)?)(к+)$', text)
        if match:
            num = float(match.group(1))
            k = len(match.group(2))
            if k == 1:
                return int(num * 1000)
            elif k == 2:
                return int(num * 1_000_000)
            elif k == 3:
                return int(num * 1_000_000_000)
        
        # Обычное число
        try:
            return int(text)
        except:
            return 0
    
    def parse_float(self, text):
        """Парсит число с плавающей точкой"""
        try:
            return float(text.replace(',', '.'))
        except:
            return 0
    
    def fmt(self, n):
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}ккк"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}кк"
        if n >= 1000:
            return f"{n/1000:.1f}к"
        return str(n)

# === СОЗДАЕМ ЭКЗЕМПЛЯР ===
bot_core = BotCore()

# === ПРОВЕРКА НА ЛС ===
def is_private(message: Message):
    return message.chat.type == 'private'

# === КОМАНДА ПОМОЩЬ ===
async def cmd_help(msg: Message):
    """Показывает список всех команд"""
    help_text = """
🎮 **ВСЕ ИГРЫ БОТА**

**💰 ИГРЫ НА ДЕНЬГИ:**
• `монетка [ставка] [орел/решка]` - классическая монетка (x2)
• `слоты [ставка]` - игровые автоматы (x5 или x10)
• `кубик [ставка] [число]` - угадай число на кубике (x6)
• `краш [ставка] [иксы]` - ракета летит до множителя
• `мины [ставка] [мин]` - минное поле с множителями
• `башня [ставка] [мин]` - башня (авто переход на след. этаж)
• `рулетка [ставка] [ставка]` - европейская рулетка

**💰 ОСОБАЯ СТАВКА:**
• `все` - поставить ВЕСЬ баланс (например: `мины все 5`)

**🏦 БАНК (только в ЛС):**
• `банк` - главное меню банка
• `карта` - баланс карты (скрытый)
• `положить [сумма]` - деньги на карту
• `снять [сумма]` - деньги с карты
• `вклад [сумма] [дни]` - открыть вклад
• `вклады` - мои вклады
• `кредит [сумма] [дни]` - взять кредит
• `кредиты` - мои кредиты

**📊 ПРОФИЛЬ И БАЛАНС:**
• `баланс` или `б` - проверить баланс (основной)
• `профиль` - полная статистика
• `п` - быстрый профиль (работает в группах)
• `топ` - топ игроков по балансу
• `топ статусы` - топ по статусам

**👑 СТАТУСЫ И БОНУСЫ:**
• `статусы` - магазин статусов
• `статус` - мой статус
• `бонус` - получить бонус (раз в час)

**🛍️ NFT МАГАЗИН (только в ЛС):**
• `магазин` - посмотреть доступные NFT
• `инвентарь` - мои NFT

**🔄 ПЕРЕВОДЫ:**
• `дать [сумма]` - перевести деньги (в ответ на сообщение)
• `передать [номер] [id]` - передать NFT

**🎫 ПРОМОКОДЫ:**
• `промо [код]` - активировать промокод

**💰 ФОРМАТЫ СТАВОК:**
• 1к = 1,000
• 1кк = 1,000,000
• 1ккк = 1,000,000,000
• `все` = весь баланс

✨ **Баланс при старте: 10,000 коинов**
"""
    await msg.answer(help_text, parse_mode="Markdown")

# === ОБРАБОТЧИКИ КОМАНД ===
async def cmd_start(msg: Message):
    bot_core.db.get(msg.from_user.id)
    await msg.answer(
        f"🎰 Добро пожаловать, {msg.from_user.first_name}!\n"
        f"💰 Баланс: {bot_core.fmt(START_BALANCE)}\n\n"
        f"📝 Основные команды:\n"
        f"• `помощь` или `help` - все команды\n"
        f"• `баланс` / `б` - проверить баланс\n"
        f"• `профиль` / `п` - статистика\n"
        f"• `банк` - банковские операции\n"
        f"• `статусы` - магазин статусов\n"
        f"• `бонус` - бонус раз в час\n"
        f"• `топ` - топ игроков\n"
        f"• `магазин` - NFT магазин (только ЛС)\n"
        f"• `инвентарь` - мои NFT (только ЛС)\n\n"
        f"🎮 Новые игры:\n"
        f"• `башня 1000 2` - башня (авто переход)\n"
        f"• `рулетка 5000 чет` - рулетка\n\n"
        f"💰 1к=1,000 | 1кк=1,000,000 | 1ккк=1,000,000,000",
        parse_mode="Markdown"
    )

async def cmd_balance(msg: Message):
    user = bot_core.db.get(msg.from_user.id)
    await msg.answer(f"💰 Основной баланс: {bot_core.fmt(user['balance'])}")

async def cmd_short_profile(msg: Message):
    """Короткий профиль (команда 'п') - работает везде"""
    user = bot_core.db.get(msg.from_user.id)
    inv = bot_core.shop.inventory(msg.from_user.id)
    games = user.get('games_played', 0)
    wins = user.get('wins', 0)
    rate = (wins/games*100) if games > 0 else 0
    
    # Получаем статус
    statuses = bot_core.status_shop.get_all_statuses()
    status = statuses.get(user.get('status', 'novice'), statuses['novice'])
    
    # Сортируем NFT по глобальному номеру
    sorted_inv = sorted(inv, key=lambda x: x.get('global_number', 0))
    
    text = f"📊 {status['emoji']} {msg.from_user.first_name}\n"
    text += f"💰 {bot_core.fmt(user['balance'])}\n"
    text += f"🎮 {games} игр | 🏆 {wins} побед | {rate:.1f}%\n\n"
    text += f"🎒 NFT ({len(inv)}):\n"
    
    for item in sorted_inv[:5]:
        text += f"#{item.get('global_number', '?')} {item['emoji']} {item['name']}\n"
    
    if len(inv) > 5:
        text += f"...и еще {len(inv)-5}\n"
    
    await msg.answer(text)

async def cmd_full_profile(msg: Message):
    """Полный профиль (команда 'профиль')"""
    user = bot_core.db.get(msg.from_user.id)
    inv = bot_core.shop.inventory(msg.from_user.id)
    games = user.get('games_played', 0)
    wins = user.get('wins', 0)
    rate = (wins/games*100) if games > 0 else 0
    
    # Получаем статус
    statuses = bot_core.status_shop.get_all_statuses()
    status = statuses.get(user.get('status', 'novice'), statuses['novice'])
    
    # Информация о бонусе
    last_bonus = user.get('last_bonus')
    bonus_info = "Не получали"
    if last_bonus:
        last_time = datetime.datetime.fromisoformat(last_bonus)
        hours_passed = (datetime.datetime.now() - last_time).total_seconds() / 3600
        if hours_passed < 1:
            next_bonus = int((1 - hours_passed) * 60)
            bonus_info = f"Через {next_bonus} мин"
        else:
            bonus_info = "Можно получить"
    
    # Сортируем NFT по глобальному номеру
    sorted_inv = sorted(inv, key=lambda x: x.get('global_number', 0))
    
    text = f"📊 ПОДРОБНЫЙ ПРОФИЛЬ {msg.from_user.first_name}\n\n"
    text += f"{status['emoji']} **{status['name']}**\n"
    text += f"   • Бонус: {bot_core.fmt(status['min_bonus'])}-{bot_core.fmt(status['max_bonus'])}/час\n"
    text += f"   • Последний бонус: {bonus_info}\n\n"
    text += f"💰 Основной баланс: {bot_core.fmt(user['balance'])}\n"
    text += f"🎮 Всего игр: {games}\n"
    text += f"🏆 Побед: {wins}\n"
    text += f"📈 Процент побед: {rate:.1f}%\n"
    text += f"🎫 Использовано промокодов: {len(user.get('used_promocodes', []))}\n\n"
    text += f"🎒 КОЛЛЕКЦИЯ NFT ({len(inv)}):\n"
    
    # Группируем по типу
    by_type = {}
    for item in sorted_inv:
        key = f"{item['item_id']} {item['emoji']} {item['name']}"
        if key not in by_type:
            by_type[key] = []
        by_type[key].append(item['global_number'])
    
    for item_key, numbers in by_type.items():
        numbers_str = ', '.join([f"#{n}" for n in sorted(numbers)])
        text += f"• {item_key}: {numbers_str}\n"
    
    await msg.answer(text, parse_mode="Markdown")

# === ИСПРАВЛЕННЫЙ ТОП С НИКАМИ ===
async def cmd_top_balance(msg: Message):
    """Топ игроков по балансу с именами"""
    top = bot_core.db.top_by_balance(10)  # Получаем топ 10
    
    if not top:
        await msg.answer("📊 Рейтинг пуст")
        return
    
    text = "🏆 **ТОП ПО БАЛАНСУ**\n\n"
    
    for i, (uid, u) in enumerate(top, 1):
        user_id = int(uid)
        balance = u.get('balance', 0)
        
        # Пытаемся получить информацию о пользователе
        try:
            # Пробуем получить через API Telegram
            chat = await msg.bot.get_chat(user_id)
            name = chat.first_name
            if chat.last_name:
                name += f" {chat.last_name}"
            # Если есть username, добавляем его в скобках
            if chat.username:
                name += f" (@{chat.username})"
        except:
            # Если не удалось получить, используем ID
            name = f"ID {user_id}"
        
        # Добавляем эмодзи для топ-3
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = "▪️"
        
        text += f"{medal} {i}. {name} - {bot_core.fmt(balance)}\n"
    
    await msg.answer(text, parse_mode="Markdown")

async def cmd_top_status(msg: Message):
    """Топ игроков по статусам с именами"""
    top = bot_core.db.top_by_status()
    statuses = bot_core.status_shop.get_all_statuses()
    
    text = "🏆 **ТОП ПО СТАТУСАМ**\n\n"
    
    # Порядок статусов (от высшего к низшему)
    status_order = ['immortal', 'oligarch', 'legend', 'vip', 'gambler', 'player', 'novice']
    status_names = {
        'immortal': '⚡ Бессмертные',
        'oligarch': '💰 Олигархи',
        'legend': '👑 Легенды',
        'vip': '💎 VIP',
        'gambler': '🎲 Азартные',
        'player': '🎮 Игроки',
        'novice': '🌱 Новички'
    }
    
    for status_id in status_order:
        if status_id in top and top[status_id]:
            status_info = statuses.get(status_id, {'emoji': '🎮', 'name': status_id})
            status_title = status_names.get(status_id, f"{status_info['emoji']} {status_info['name']}")
            text += f"**{status_title}:**\n"
            
            for i, (uid, u) in enumerate(top[status_id][:3], 1):
                user_id = int(uid)
                balance = u.get('balance', 0)
                
                # Пытаемся получить информацию о пользователе
                try:
                    chat = await msg.bot.get_chat(user_id)
                    name = chat.first_name
                    if chat.last_name:
                        name += f" {chat.last_name}"
                except:
                    name = f"ID {user_id}"
                
                text += f"   {i}. {name} - {bot_core.fmt(balance)}\n"
            text += "\n"
    
    await msg.answer(text, parse_mode="Markdown")

# === СТАТУСЫ ===
async def cmd_status_shop(msg: Message):
    """Магазин статусов"""
    if not is_private(msg):
        await msg.answer("❌ Магазин статусов доступен только в личных сообщениях с ботом!")
        return
    
    user = bot_core.db.get(msg.from_user.id)
    statuses = bot_core.status_shop.get_all_statuses()
    
    text = f"🏪 **МАГАЗИН СТАТУСОВ**\n\n"
    text += f"Ваш текущий статус: {statuses[user['status']]['emoji']} {statuses[user['status']]['name']}\n"
    text += f"💰 Баланс: {bot_core.fmt(user['balance'])}\n\n"
    text += "Доступные статусы:\n\n"
    
    kb = []
    for status_id, status in statuses.items():
        if status_id == user['status']:
            text += f"{status['emoji']} {status['name']} — {bot_core.fmt(status['price'])}\n"
            text += f"   • Бонус: {bot_core.fmt(status['min_bonus'])}-{bot_core.fmt(status['max_bonus'])}\n"
            text += f"   • Уже есть\n\n"
        else:
            kb.append([InlineKeyboardButton(
                text=f"{status['emoji']} {status['name']} — {bot_core.fmt(status['price'])}",
                callback_data=f"status_view_{status_id}"
            )])
    
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

async def cmd_my_status(msg: Message):
    """Показать свой статус"""
    user = bot_core.db.get(msg.from_user.id)
    statuses = bot_core.status_shop.get_all_statuses()
    status = statuses.get(user['status'], statuses['novice'])
    
    # Информация о бонусе
    last_bonus = user.get('last_bonus')
    bonus_info = "Никогда"
    if last_bonus:
        last_time = datetime.datetime.fromisoformat(last_bonus)
        hours_passed = (datetime.datetime.now() - last_time).total_seconds() / 3600
        if hours_passed < 1:
            next_bonus = int((1 - hours_passed) * 60)
            bonus_info = f"Через {next_bonus} мин"
        else:
            bonus_info = "Можно получить сейчас!"
    
    text = f"{status['emoji']} **{status['name']}**\n\n"
    text += f"💰 Бонус: {bot_core.fmt(status['min_bonus'])} - {bot_core.fmt(status['max_bonus'])} (каждый час)\n"
    text += f"⏰ Последний бонус: {bonus_info}\n"
    text += f"📝 {status['description']}"
    
    await msg.answer(text, parse_mode="Markdown")

async def cmd_bonus(msg: Message):
    """Получить бонус"""
    user_id = msg.from_user.id
    user = bot_core.db.get(user_id)
    statuses = bot_core.status_shop.get_all_statuses()
    status = statuses.get(user['status'], statuses['novice'])
    
    # Проверяем, прошло ли достаточно времени
    last_bonus = user.get('last_bonus')
    if last_bonus:
        last_time = datetime.datetime.fromisoformat(last_bonus)
        hours_passed = (datetime.datetime.now() - last_time).total_seconds() / 3600
        if hours_passed < 1:
            next_bonus = int((1 - hours_passed) * 60)
            await msg.answer(f"⏰ Бонус еще не доступен!\nСледующий бонус через {next_bonus} минут.")
            return
    
    # Генерируем бонус
    bonus = random.randint(status['min_bonus'], status['max_bonus'])
    new_balance = user['balance'] + bonus
    
    # Обновляем данные
    user['last_bonus'] = datetime.datetime.now().isoformat()
    user['bonus_history'].append({
        'amount': bonus,
        'time': datetime.datetime.now().isoformat()
    })
    bot_core.db.update(user_id, balance=new_balance, last_bonus=user['last_bonus'], bonus_history=user['bonus_history'])
    
    await msg.answer(
        f"🎁 **ЕЖЕЧАСНЫЙ БОНУС**\n\n"
        f"Ваш статус: {status['emoji']} {status['name']}\n"
        f"Вы получили: +{bot_core.fmt(bonus)}\n\n"
        f"💰 Новый баланс: {bot_core.fmt(new_balance)}\n"
        f"⏰ Следующий бонус через: 60 мин",
        parse_mode="Markdown"
    )

# === БАНК ===
async def cmd_bank(msg: Message, state: FSMContext):
    """Главное меню банка"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    user_id = msg.from_user.id
    bank_menu = bot_core.bank.get_bank_menu(user_id)
    
    kb = [
        [InlineKeyboardButton(text="💳 Карта", callback_data="bank_card"),
         InlineKeyboardButton(text="📈 Вклады", callback_data="bank_deposits")],
        [InlineKeyboardButton(text="📉 Кредиты", callback_data="bank_loans"),
         InlineKeyboardButton(text="❓ Помощь", callback_data="bank_help")]
    ]
    
    await msg.answer(bank_menu, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

async def cmd_card_balance(msg: Message):
    """Показать баланс карты"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    user_id = msg.from_user.id
    user_bank = bot_core.bank.get_user_bank(user_id)
    
    await msg.answer(f"💳 **Баланс карты**: {bot_core.fmt(user_bank['card_balance'])}\n\n"
                    f"Эти деньги не видны другим игрокам и не участвуют в играх.",
                    parse_mode="Markdown")

async def cmd_card_deposit(msg: Message, command: CommandObject, state: FSMContext):
    """Положить деньги на карту"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 1:
        await msg.answer("Использование: положить [сумма]\nПример: положить 10000")
        return
    
    user_id = msg.from_user.id
    user = bot_core.db.get(user_id)
    amount = bot_core.parse_bet(args[0], user['balance'])
    
    if amount <= 0:
        await msg.answer("❌ Неверная сумма!")
        return
    
    res = bot_core.bank.card_deposit(user_id, amount, user['balance'])
    if res['ok']:
        # Списываем с основного счета
        new_balance = user['balance'] - amount
        bot_core.db.update(user_id, balance=new_balance)
        await msg.answer(res['msg'], parse_mode="Markdown")
    else:
        await msg.answer(res['msg'])

async def cmd_card_withdraw(msg: Message, command: CommandObject, state: FSMContext):
    """Снять деньги с карты"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 1:
        await msg.answer("Использование: снять [сумма]\nПример: снять 5000")
        return
    
    user_id = msg.from_user.id
    user = bot_core.db.get(user_id)
    amount = bot_core.parse_bet(args[0])
    
    if amount <= 0:
        await msg.answer("❌ Неверная сумма!")
        return
    
    res = bot_core.bank.card_withdraw(user_id, amount, user['balance'])
    if res['ok']:
        # Добавляем на основной счет
        new_balance = user['balance'] + amount
        bot_core.db.update(user_id, balance=new_balance)
        await msg.answer(res['msg'], parse_mode="Markdown")
    else:
        await msg.answer(res['msg'])

async def cmd_deposit_create(msg: Message, command: CommandObject, state: FSMContext):
    """Создать вклад"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await msg.answer("Использование: вклад [сумма] [дни]\n"
                        "Доступные сроки: 7, 14, 30, 90, 180, 365 дней")
        return
    
    user_id = msg.from_user.id
    user = bot_core.db.get(user_id)
    amount = bot_core.parse_bet(args[0], user['balance'])
    days = int(args[1])
    
    if amount <= 0:
        await msg.answer("❌ Неверная сумма!")
        return
    
    res = bot_core.bank.create_deposit(user_id, amount, days, user['balance'])
    if res['ok']:
        # Списываем с основного счета
        new_balance = user['balance'] - amount
        bot_core.db.update(user_id, balance=new_balance)
        await msg.answer(res['msg'], parse_mode="Markdown")
    else:
        await msg.answer(res['msg'])

async def cmd_deposit_list(msg: Message):
    """Список активных вкладов"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    user_id = msg.from_user.id
    user_bank = bot_core.bank.get_user_bank(user_id)
    
    active_deposits = [d for d in user_bank['deposits'] if d['status'] == 'active']
    
    if not active_deposits:
        await msg.answer("📭 У вас нет активных вкладов")
        return
    
    text = "📈 **АКТИВНЫЕ ВКЛАДЫ**\n\n"
    kb = []
    
    for dep in active_deposits:
        end_date = datetime.datetime.fromisoformat(dep['end_date'])
        days_left = (end_date - datetime.datetime.now()).days
        text += f"ID: `{dep['id']}`\n"
        text += f"💰 Сумма: {bot_core.fmt(dep['amount'])}\n"
        text += f"📈 Ставка: {dep['rate']}%\n"
        text += f"⏰ Осталось: {days_left} дней\n"
        text += f"📅 Выплата: {end_date.strftime('%d.%m.%Y')}\n\n"
        
        kb.append([InlineKeyboardButton(
            text=f"❌ Закрыть {dep['id']}", 
            callback_data=f"close_deposit_{dep['id']}"
        )])
    
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
    
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

async def cmd_loan_create(msg: Message, command: CommandObject, state: FSMContext):
    """Взять кредит"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await msg.answer("Использование: кредит [сумма] [дни]\n"
                        "Доступные сроки: 7, 14, 30, 90, 180, 365 дней")
        return
    
    user_id = msg.from_user.id
    user = bot_core.db.get(user_id)
    amount = bot_core.parse_bet(args[0])
    days = int(args[1])
    
    if amount <= 0:
        await msg.answer("❌ Неверная сумма!")
        return
    
    res = bot_core.bank.create_loan(user_id, amount, days, user['balance'])
    if res['ok']:
        # Добавляем на основной счет
        new_balance = user['balance'] + amount
        bot_core.db.update(user_id, balance=new_balance)
        await msg.answer(res['msg'], parse_mode="Markdown")
    else:
        await msg.answer(res['msg'])

async def cmd_loan_list(msg: Message):
    """Список активных кредитов"""
    if not is_private(msg):
        await msg.answer("❌ Банк доступен только в личных сообщениях с ботом!")
        return
    
    user_id = msg.from_user.id
    user_bank = bot_core.bank.get_user_bank(user_id)
    
    active_loans = [l for l in user_bank['loans'] if l['status'] == 'active']
    
    if not active_loans:
        await msg.answer("📭 У вас нет активных кредитов")
        return
    
    text = "📉 **АКТИВНЫЕ КРЕДИТЫ**\n\n"
    kb = []
    
    for loan in active_loans:
        end_date = datetime.datetime.fromisoformat(loan['end_date'])
        days_left = (end_date - datetime.datetime.now()).days
        text += f"ID: `{loan['id']}`\n"
        text += f"💰 Сумма: {bot_core.fmt(loan['amount'])}\n"
        text += f"💵 Осталось: {bot_core.fmt(loan['remaining'])}\n"
        text += f"📈 Ставка: {loan['rate']}%\n"
        text += f"⏰ Осталось: {days_left} дней\n"
        text += f"📆 Ежедневный платеж: {bot_core.fmt(loan['daily_payment'])}\n\n"
        
        kb.append([InlineKeyboardButton(
            text=f"💸 Оплатить {loan['id']}", 
            callback_data=f"pay_loan_{loan['id']}"
        )])
    
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
    
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

# === МАГАЗИН NFT ===
async def cmd_shop(msg: Message):
    """Показать магазин NFT"""
    if not is_private(msg):
        await msg.answer("❌ Магазин доступен только в личных сообщениях с ботом!\nПерейдите в ЛС: @DropPepebot")
        return
    
    user_id = msg.from_user.id
    user = bot_core.db.get(user_id)
    items = bot_core.shop.items()
    
    if not items:
        await msg.answer("🛍️ Магазин пуст")
        return
    
    # Отладка
    print(f"DEBUG: Shop opened by user {user_id}, balance: {user['balance']}")
    
    kb = []
    for id, item in items.items():
        if item.get('quantity', 0) > 0:
            price_str = bot_core.fmt(item.get('price', 0))
            kb.append([InlineKeyboardButton(
                text=f"{item.get('emoji', '🎁')} {item.get('name', 'Товар')} | {price_str}",
                callback_data=f"shop_view_{id}"
            )])
    
    kb.append([InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="shop_my_inv")])
    
    await msg.answer(
        "🛍️ **МАГАЗИН NFT**\n\n"
        f"💰 Ваш баланс: {bot_core.fmt(user['balance'])}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )

async def cmd_inventory(msg: Message):
    """Показать инвентарь пользователя"""
    if not is_private(msg):
        await msg.answer("❌ Инвентарь доступен только в личных сообщениях с ботом!\nПерейдите в ЛС: @DropPepebot")
        return
    
    user_id = msg.from_user.id
    print(f"DEBUG: Checking inventory for user {user_id}")
    
    # Получаем инвентарь
    inv = bot_core.shop.inventory(user_id)
    
    # Отладка
    print(f"DEBUG: Found {len(inv)} items in inventory")
    for item in inv:
        print(f"  - #{item.get('global_number')} {item.get('name')} ({item.get('unique_id')})")
    
    if not inv:
        await msg.answer("🎒 Ваш инвентарь пуст")
        return
    
    # Сортируем по глобальному номеру
    sorted_inv = sorted(inv, key=lambda x: x.get('global_number', 0))
    
    kb = []
    for item in sorted_inv:
        global_num = item.get('global_number', '?')
        item_name = item.get('name', 'Неизвестно')
        item_emoji = item.get('emoji', '🎁')
        unique_id = item.get('unique_id', '')
        
        kb.append([InlineKeyboardButton(
            text=f"#{global_num} {item_emoji} {item_name}",
            callback_data=f"inv_view_{unique_id}"
        )])
    
    await msg.answer(
        "🎒 **ВАШ ИНВЕНТАРЬ**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )

async def cmd_give(msg: Message):
    """Перевести деньги другому пользователю (ответом на сообщение)"""
    if not msg.reply_to_message:
        await msg.answer("❌ Эта команда работает только как ответ на сообщение пользователя!\n"
                        "Нажмите на сообщение человека и выберите 'Ответить', затем напишите 'дать 1000'")
        return
    
    recipient_id = msg.reply_to_message.from_user.id
    sender_id = msg.from_user.id
    
    if sender_id == recipient_id:
        await msg.answer("❌ Нельзя переводить деньги самому себе!")
        return
    
    text = msg.text.strip().lower()
    parts = text.split()
    
    if len(parts) != 2 or parts[0] not in ['дать', 'дай']:
        await msg.answer("❌ Неверный формат. Используйте: дать [сумма]\n"
                        "Пример: дать 10к")
        return
    
    sender = bot_core.db.get(sender_id)
    amount = bot_core.parse_bet(parts[1], sender['balance'])
    
    if amount <= 0:
        await msg.answer("❌ Неверная сумма перевода!")
        return
    
    if sender['balance'] < amount:
        await msg.answer(f"❌ Недостаточно средств! Ваш баланс: {bot_core.fmt(sender['balance'])}")
        return
    
    recipient = bot_core.db.get(recipient_id)
    
    new_sender_balance = sender['balance'] - amount
    new_recipient_balance = recipient['balance'] + amount
    
    bot_core.db.update(sender_id, balance=new_sender_balance)
    bot_core.db.update(recipient_id, balance=new_recipient_balance)
    
    await msg.reply(f"✅ Перевод выполнен!\n"
                    f"➖ Вы отправили: {bot_core.fmt(amount)}\n"
                    f"➕ Получатель: {msg.reply_to_message.from_user.full_name}\n"
                    f"💰 Ваш новый баланс: {bot_core.fmt(new_sender_balance)}")
    
    try:
        await msg.bot.send_message(
            recipient_id,
            f"🎁 Вам перевели {bot_core.fmt(amount)}!\n"
            f"📤 Отправитель: {msg.from_user.full_name}\n"
            f"💰 Ваш новый баланс: {bot_core.fmt(new_recipient_balance)}"
        )
    except:
        pass

async def cmd_promo(msg: Message, command: CommandObject):
    """Активировать промокод"""
    if not command.args:
        await msg.answer("Использование: промо КОД")
        return
    code = command.args.upper().strip()
    res = bot_core.promo.use(code, msg.from_user.id, bot_core.db)
    await msg.answer(res['msg'])

async def cmd_transfer(msg: Message, command: CommandObject):
    """Передать NFT другому пользователю"""
    if not is_private(msg):
        await msg.answer("❌ Передача NFT доступна только в личных сообщениях с ботом!")
        return
    
    args = command.args.split() if command.args else []
    
    if len(args) != 2:
        inv = bot_core.shop.inventory(msg.from_user.id)
        if not inv:
            await msg.answer("🎒 Ваш инвентарь пуст")
            return
        
        text = "🔄 **ПЕРЕДАЧА NFT**\n\n"
        text += "Ваши NFT:\n"
        for i, item in enumerate(inv, 1):
            text += f"{i}. #{item.get('global_number', '?')} {item['emoji']} {item['name']}\n"
        text += "\nИспользуйте: `/transfer [номер] [id_получателя]`\n"
        text += "Или выберите NFT в инвентаре и нажмите 'Передать'"
        await msg.answer(text, parse_mode="Markdown")
        return
    
    try:
        idx = int(args[0]) - 1
        recipient_id = int(args[1])
        
        inv = bot_core.shop.inventory(msg.from_user.id)
        if idx < 0 or idx >= len(inv):
            await msg.answer("❌ Неверный номер NFT!")
            return
        
        item = inv[idx]
        unique_id = item['unique_id']
        
        item_data, owner_id = bot_core.shop.get_item_by_unique_id(unique_id)
        if not item_data or owner_id != msg.from_user.id:
            await msg.answer("❌ Предмет не найден в вашем инвентаре!")
            return
        
        if recipient_id == msg.from_user.id:
            await msg.answer("❌ Нельзя передать предмет самому себе!")
            return
        
        # Удаляем у отправителя
        bot_core.shop.remove_from_inventory(msg.from_user.id, unique_id)
        
        # Добавляем получателю
        bot_core.shop.add_to_inventory(recipient_id, item_data)
        
        await msg.answer(
            f"✅ NFT передан!\n\n"
            f"#{item_data['global_number']} {item_data['emoji']} {item_data['name']}\n"
            f"📤 Получатель: ID {recipient_id}"
        )
        
        # Уведомляем получателя
        try:
            await msg.bot.send_message(
                recipient_id,
                f"🎁 Вам передали NFT!\n\n"
                f"#{item_data['global_number']} {item_data['emoji']} {item_data['name']}\n"
                f"📤 Отправитель: {msg.from_user.full_name}"
            )
        except:
            pass
            
    except ValueError:
        await msg.answer("❌ Неверный формат. Используйте: /transfer [номер] [id]")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

# === ИГРЫ (С ОТВЕТОМ НА СООБЩЕНИЕ) ===
async def cmd_coin(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) == 2:
        bet = bot_core.parse_bet(args[0], balance)
        choice = args[1].lower().replace('ё', 'е')
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        if choice not in ['орел', 'решка']:
            await msg.reply("❌ Неверный выбор. Выберите 'орел' или 'решка'")
            return
        res = bot_core.games.coin(msg.from_user.id, bet, choice)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        if res['win']:
            await msg.reply(f"🎉 {msg.from_user.first_name}, выпал {res['res']}! +{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
        else:
            await msg.reply(f"😞 {msg.from_user.first_name}, выпал {res['res']}! -{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
    elif len(args) == 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🦅 Орел", callback_data=f"coin_{bet}_орел")],
            [InlineKeyboardButton(text="🪙 Решка", callback_data=f"coin_{bet}_решка")]
        ])
        await msg.reply(f"💰 {msg.from_user.first_name}, ставка: {bot_core.fmt(bet)}\nВыберите сторону:", reply_markup=kb)
    else:
        await msg.reply("Использование: монетка СТАВКА [орел/решка]\nПример: монетка 1кк орел")

async def cmd_slots(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) >= 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        res = bot_core.games.slots(msg.from_user.id, bet)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        reels = ' | '.join(res['reels'])
        if res['win']:
            await msg.reply(f"🎰 {msg.from_user.first_name}, {reels}\n🎉 ДЖЕКПОТ x{res['mult']}! +{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
        else:
            await msg.reply(f"🎰 {msg.from_user.first_name}, {reels}\n😞 Проигрыш: -{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
    else:
        await msg.reply("Использование: слоты СТАВКА\nПример: слоты 1кк")

async def cmd_dice(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) == 2:
        bet = bot_core.parse_bet(args[0], balance)
        pred = int(args[1])
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        if pred < 1 or pred > 6:
            await msg.reply("❌ Число должно быть от 1 до 6!")
            return
        res = bot_core.games.dice(msg.from_user.id, bet, pred)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        if res['win']:
            await msg.reply(f"🎲 {msg.from_user.first_name}, выпало {res['roll']}! +{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
        else:
            await msg.reply(f"🎲 {msg.from_user.first_name}, выпало {res['roll']}! -{bot_core.fmt(res['amount'])}\n💰 Баланс: {bot_core.fmt(res['balance'])}")
    elif len(args) == 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(1,4)],
            [InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(4,7)]
        ])
        await msg.reply(f"💰 {msg.from_user.first_name}, ставка: {bot_core.fmt(bet)}\nВыберите число:", reply_markup=kb)
    else:
        await msg.reply("Использование: кубик СТАВКА ЧИСЛО\nПример: кубик 1кк 5")

async def cmd_crash(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) == 2:
        bet = bot_core.parse_bet(args[0], balance)
        target_x = bot_core.parse_float(args[1])
        
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        
        if target_x < 1.1:
            await msg.reply("❌ Минимальный множитель: 1.1x")
            return
        
        if target_x > 100:
            await msg.reply("❌ Максимальный множитель: 100x")
            return
        
        res = bot_core.crash.start(msg.from_user.id, bet, target_x)
        
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        game = res['game_data']
        crash = game['crash_point']
        
        if game['status'] == 'won':
            await msg.reply(
                f"🚀 {msg.from_user.first_name}, КРАШ! Ракета улетела на x{crash}!\n\n"
                f"✅ Ваш множитель x{target_x} достигнут!\n"
                f"💰 Выигрыш: +{bot_core.fmt(game['win_amount'])}\n"
                f"💵 Новый баланс: {bot_core.fmt(game['final_balance'])}"
            )
        else:
            await msg.reply(
                f"💥 {msg.from_user.first_name}, КРАШ! Ракета улетела на x{crash}...\n\n"
                f"❌ Вы не успели забрать (цель была x{target_x})\n"
                f"💸 Проигрыш: -{bot_core.fmt(bet)}\n"
                f"💵 Баланс: {bot_core.fmt(game['final_balance'])}"
            )
    
    elif len(args) == 1:
        bet = bot_core.parse_bet(args[0], balance)
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1.5x", callback_data=f"crash_{bet}_1.5"),
             InlineKeyboardButton(text="2x", callback_data=f"crash_{bet}_2"),
             InlineKeyboardButton(text="3x", callback_data=f"crash_{bet}_3")],
            [InlineKeyboardButton(text="5x", callback_data=f"crash_{bet}_5"),
             InlineKeyboardButton(text="10x", callback_data=f"crash_{bet}_10"),
             InlineKeyboardButton(text="20x", callback_data=f"crash_{bet}_20")]
        ])
        await msg.reply(
            f"🚀 {msg.from_user.first_name}, КРАШ\n\n"
            f"💰 Ставка: {bot_core.fmt(bet)}\n"
            f"Выберите множитель:",
            reply_markup=kb
        )
    
    else:
        await msg.reply(
            "🚀 ИГРА КРАШ\n\n"
            "Правила:\n"
            "• Выбираете ставку и множитель\n"
            "• Ракета взлетает со случайным множителем\n"
            "• Если множитель >= вашему - выигрыш\n"
            "• Если множитель < вашему - проигрыш\n\n"
            "Использование: краш СТАВКА [иксы]\n"
            "Пример: краш 1кк 2\n"
            "Пример: краш 500к 5.5\n"
            "Пример: краш все 2 - поставить всё!"
        )

async def cmd_mines(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) >= 1:
        bet = bot_core.parse_bet(args[0], balance)
        mines = int(args[1]) if len(args) > 1 else 3
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        if mines < 1 or mines > 24:
            await msg.reply("❌ Количество мин должно быть от 1 до 24!")
            return
        res = bot_core.mines.start(msg.from_user.id, bet, mines)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        kb = bot_core.mines.kb(msg.from_user.id, res['data']['field'])
        await msg.reply(
            f"🎮 {msg.from_user.first_name}, Мины | 💣 {mines}\n"
            f"💰 Ставка: {bot_core.fmt(bet)}\n"
            f"📈 x1.0 | 💎 0",
            reply_markup=kb
        )
    else:
        await msg.reply(
            "🎮 МИНЫ\n"
            "Правила: открывайте клетки, множитель растёт\n"
            "💣 мина - проигрыш\n\n"
            "Использование: мины СТАВКА [МИН]\n"
            "Пример: мины 1кк 5\n"
            "Пример: мины все 10 - поставить всё на 10 мин"
        )

async def cmd_tower(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) >= 1:
        bet = bot_core.parse_bet(args[0], balance)
        mines = int(args[1]) if len(args) > 1 else 1
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        if mines < 1 or mines > 4:
            await msg.reply("❌ Количество мин должно быть от 1 до 4!")
            return
        
        res = bot_core.tower.start(msg.from_user.id, bet, mines)
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        kb = bot_core.tower.create_keyboard(msg.from_user.id, res['data'])
        await msg.reply(
            f"🏗️ {msg.from_user.first_name}, БАШНЯ | Этаж 1/9 | 💣 {mines}\n"
            f"💰 Ставка: {bot_core.fmt(bet)}\n"
            f"📈 x1.0 | 💎 0\n\n"
            f"Выберите клетку (авто переход на след. этаж):",
            reply_markup=kb
        )
    else:
        await msg.reply(
            "🏗️ ИГРА БАШНЯ\n\n"
            "Правила:\n"
            "• На каждом этаже 5 клеток, в некоторых мины\n"
            "• Открываете ОДНУ клетку на этаже\n"
            "• Автоматический переход на следующий этаж\n"
            "• Все пройденные этажи остаются видимыми\n"
            "• С каждым этажом множитель растёт\n"
            "• Максимум 9 этажей\n\n"
            "Использование: башня СТАВКА [МИН НА ЭТАЖ]\n"
            "Пример: башня 1кк 2\n"
            "Пример: башня все 1"
        )

async def cmd_roulette(msg: Message, command: CommandObject):
    args = command.args.split() if command.args else []
    
    user = bot_core.db.get(msg.from_user.id)
    balance = user['balance']
    
    if len(args) >= 2:
        bet = bot_core.parse_bet(args[0], balance)
        bet_type = args[1].lower()
        
        if bet <= 0 or bet > balance:
            await msg.reply(f"❌ Неверная ставка! Ваш баланс: {bot_core.fmt(balance)}")
            return
        
        # Проверяем тип ставки
        valid_types = ['чет', 'нечет', 'even', 'odd', 'красное', 'red', 'чёрное', 'black', 
                      '1-12', '13-24', '25-36', 'дюжина1', 'дюжина2', 'дюжина3', 
                      'колонка1', 'колонка2', 'колонка3', 'зеро', 'zero']
        
        bet_value = None
        if bet_type not in valid_types:
            # Проверяем, может быть это число
            try:
                num = int(bet_type)
                if 0 <= num <= 36:
                    bet_type = 'number'
                    bet_value = num
                else:
                    await msg.reply("❌ Неверный тип ставки! Используйте /roulette для списка ставок")
                    return
            except:
                await msg.reply("❌ Неверный тип ставки! Используйте /roulette для списка ставок")
                return
        
        # Нормализуем тип ставки
        type_map = {
            'чет': 'even', 'even': 'even',
            'нечет': 'odd', 'odd': 'odd',
            'красное': 'red', 'red': 'red',
            'чёрное': 'black', 'black': 'black',
            '1-12': '1-12', '13-24': '13-24', '25-36': '25-36',
            'дюжина1': 'dozen1', 'дюжина2': 'dozen2', 'дюжина3': 'dozen3',
            'колонка1': 'column1', 'колонка2': 'column2', 'колонка3': 'column3',
            'зеро': 'zero', 'zero': 'zero'
        }
        
        if bet_type in type_map:
            bet_type = type_map[bet_type]
        
        res = bot_core.roulette.play(msg.from_user.id, bet, bet_type, bet_value)
        
        if not res['ok']:
            await msg.reply(res['msg'])
            return
        
        color_emoji = '🟢' if res['color'] == 'green' else ('🔴' if res['color'] == 'red' else '⚫')
        
        if res['win']:
            await msg.reply(
                f"🎰 {msg.from_user.first_name}, РУЛЕТКА\n\n"
                f"Выпало: {color_emoji} {res['number']}\n\n"
                f"✅ ВЫИГРЫШ! x{res['multiplier']}\n"
                f"💰 +{bot_core.fmt(res['amount'])}\n"
                f"💵 Новый баланс: {bot_core.fmt(res['balance'])}"
            )
        else:
            await msg.reply(
                f"🎰 {msg.from_user.first_name}, РУЛЕТКА\n\n"
                f"Выпало: {color_emoji} {res['number']}\n\n"
                f"❌ ПРОИГРЫШ\n"
                f"💸 -{bot_core.fmt(res['amount'])}\n"
                f"💵 Баланс: {bot_core.fmt(res['balance'])}"
            )
    
    else:
        help_text = """
🎰 **РУЛЕТКА**

**Типы ставок и множители:**

• Чет/Нечет (even/odd) — x2
• Красное/Чёрное (red/black) — x2
• Дюжины (1-12, 13-24, 25-36) — x3
• Колонки (column1/2/3) — x3
• Зеро (zero) — x36
• Точное число (0-36) — x36

**Примеры:**
• `рулетка 1000 чет`
• `рулетка 5000 красное`
• `рулетка 1кк 7`
• `рулетка все зеро`
"""
        await msg.reply(help_text, parse_mode="Markdown")

# === CALLBACK ===
# === ИСПРАВЛЕННЫЙ CALLBACK ОБРАБОТЧИК ===
async def callback_handler(cb: CallbackQuery, state: FSMContext):
    data = cb.data
    
    try:
        # === БАНК ===
        if data == "bank_card":
            user_id = cb.from_user.id
            user_bank = bot_core.bank.get_user_bank(user_id)
            
            kb = [
                [InlineKeyboardButton(text="💰 Положить", callback_data="bank_card_deposit"),
                 InlineKeyboardButton(text="💸 Снять", callback_data="bank_card_withdraw")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]
            ]
            
            await cb.message.edit_text(
                f"💳 **БАНКОВСКАЯ КАРТА**\n\n"
                f"Баланс карты: {bot_core.fmt(user_bank['card_balance'])}\n"
                f"(эти деньги не видны другим игрокам)",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                parse_mode="Markdown"
            )
        
        elif data == "bank_deposits":
            await cmd_deposit_list(cb.message)
        
        elif data == "bank_loans":
            await cmd_loan_list(cb.message)
        
        elif data == "bank_help":
            kb = [[InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]]
            await cb.message.edit_text(
                "🏦 **ПОМОЩЬ ПО БАНКУ**\n\n"
                "💳 **Карта** - скрытый счет, не участвует в играх\n"
                "   • `положить [сумма]` - деньги на карту\n"
                "   • `снять [сумма]` - деньги с карты\n\n"
                "📈 **Вклады** - пассивный доход\n"
                "   • 7 дней: +3%\n"
                "   • 14 дней: +4.5%\n"
                "   • 30 дней: +6%\n"
                "   • 90 дней: +8%\n"
                "   • 180 дней: +10%\n"
                "   • 365 дней: +12%\n\n"
                "📉 **Кредиты** - быстрые деньги\n"
                "   • Чем выше рейтинг, тем лучше условия\n"
                "   • Просрочка ухудшает рейтинг\n"
                "   • Своевременная оплата повышает рейтинг",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        
        elif data == "bank_back":
            await cmd_bank(cb.message, state)
        
        elif data.startswith("close_deposit_"):
            deposit_id = data[14:]
            user_id = cb.from_user.id
            res = bot_core.bank.close_deposit(user_id, deposit_id)
            
            if res['ok']:
                # Возвращаем деньги на основной счет
                user = bot_core.db.get(user_id)
                new_balance = user['balance'] + res['amount']
                bot_core.db.update(user_id, balance=new_balance)
                await cb.answer(res['msg'], show_alert=True)
                await cmd_deposit_list(cb.message)
            else:
                await cb.answer(res['msg'], show_alert=True)
        
        elif data.startswith("pay_loan_"):
            loan_id = data[9:]
            await state.update_data(pay_loan_id=loan_id)
            await state.set_state(BankStates.waiting_loan_payment)
            await cb.message.edit_text(
                "💸 Введите сумму для оплаты кредита:\n"
                "Пример: 5000, 10к, 1.5кк\n\n"
                "❌ Для отмены отправьте /cancel"
            )
        
        # === ИГРЫ ===
        elif data.startswith('coin_'):
            parts = data.split('_')
            if len(parts) == 3:
                try:
                    bet = int(parts[1])
                    choice = parts[2]
                    res = bot_core.games.coin(cb.from_user.id, bet, choice)
                    if res['ok']:
                        if res['win']:
                            await cb.message.edit_text(f"🎉 {cb.from_user.first_name}, выпал {res['res']}! +{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
                        else:
                            await cb.message.edit_text(f"😞 {cb.from_user.first_name}, выпал {res['res']}! -{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
                except:
                    await cb.answer("❌ Ошибка")
        
        elif data.startswith('dice_'):
            parts = data.split('_')
            if len(parts) == 3:
                try:
                    bet = int(parts[1])
                    pred = int(parts[2])
                    res = bot_core.games.dice(cb.from_user.id, bet, pred)
                    if res['ok']:
                        if res['win']:
                            await cb.message.edit_text(f"🎲 {cb.from_user.first_name}, выпало {res['roll']}! +{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
                        else:
                            await cb.message.edit_text(f"🎲 {cb.from_user.first_name}, выпало {res['roll']}! -{bot_core.fmt(res['amount'])}\n💰 {bot_core.fmt(res['balance'])}")
                except:
                    await cb.answer("❌ Ошибка")
        
        elif data.startswith('crash_'):
            parts = data.split('_')
            if len(parts) == 3:
                try:
                    bet = int(parts[1])
                    target_x = float(parts[2])
                    
                    res = bot_core.crash.start(cb.from_user.id, bet, target_x)
                    
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    
                    game = res['game_data']
                    crash = game['crash_point']
                    
                    if game['status'] == 'won':
                        await cb.message.edit_text(
                            f"🚀 {cb.from_user.first_name}, КРАШ! Ракета улетела на x{crash}!\n\n"
                            f"✅ Ваш множитель x{target_x} достигнут!\n"
                            f"💰 Выигрыш: +{bot_core.fmt(game['win_amount'])}\n"
                            f"💵 Новый баланс: {bot_core.fmt(game['final_balance'])}"
                        )
                    else:
                        await cb.message.edit_text(
                            f"💥 {cb.from_user.first_name}, КРАШ! Ракета улетела на x{crash}...\n\n"
                            f"❌ Вы не успели забрать (цель была x{target_x})\n"
                            f"💸 Проигрыш: -{bot_core.fmt(bet)}\n"
                            f"💵 Баланс: {bot_core.fmt(game['final_balance'])}"
                        )
                except Exception as e:
                    await cb.answer(f"❌ Ошибка: {e}")
        
        elif data.startswith('mines_'):
            parts = data.split('_')
            if len(parts) >= 4:
                try:
                    user_id = int(parts[1])
                    if cb.from_user.id != user_id:
                        await cb.answer("❌ Это не ваша игра!", show_alert=True)
                        return
                    row = int(parts[2])
                    col = int(parts[3])
                    res = bot_core.mines.open(user_id, row, col)
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    if res.get('over'):
                        kb = bot_core.mines.kb(user_id, res['field'], False)
                        await cb.message.edit_text(
                            f"💥 {cb.from_user.first_name}, БУМ! Проигрыш: {bot_core.fmt(res['bet'])}\n"
                            f"🎯 Открыто: {res['opened']}",
                            reply_markup=kb
                        )
                    else:
                        kb = bot_core.mines.kb(user_id, res['field'])
                        game = bot_core.mines.games.get(user_id)
                        if game:
                            await cb.message.edit_text(
                                f"🎮 {cb.from_user.first_name}, Мины | 💣 {game['count']}\n"
                                f"💰 Ставка: {bot_core.fmt(game['bet'])}\n"
                                f"🎯 {res['opened']}/{res['max']} | 📈 x{res['mult']:.2f}\n"
                                f"💎 {bot_core.fmt(res['won'])}",
                                reply_markup=kb
                            )
                except Exception as e:
                    await cb.answer(f"❌ Ошибка: {e}")
        
        elif data.startswith('cashout_'):
            parts = data.split('_')
            if len(parts) == 2:
                try:
                    user_id = int(parts[1])
                    if cb.from_user.id != user_id:
                        await cb.answer("❌ Это не ваша игра!", show_alert=True)
                        return
                    res = bot_core.mines.cashout(user_id)
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    kb = bot_core.mines.kb(user_id, res['field'], False)
                    await cb.message.edit_text(
                        f"🏆 {cb.from_user.first_name}, Выигрыш: +{bot_core.fmt(res['won'])}\n"
                        f"🎯 {res['opened']} | 📈 x{res['mult']:.2f}\n"
                        f"💰 Баланс: {bot_core.fmt(res['balance'])}",
                        reply_markup=kb
                    )
                except:
                    await cb.answer("❌ Ошибка")
        
        elif data == "mines_new":
            await cb.message.edit_text("🎮 Используй: мины СТАВКА [МИН]")
        
        # === БАШНЯ ===
        elif data.startswith('tower_open_'):
            parts = data.split('_')
            if len(parts) == 5:
                try:
                    user_id = int(parts[2])
                    if cb.from_user.id != user_id:
                        await cb.answer("❌ Это не ваша игра!", show_alert=True)
                        return
                    row = int(parts[3])
                    col = int(parts[4])
                    
                    res = bot_core.tower.open_cell(user_id, row, col)
                    
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    
                    if res.get('over'):
                        if res.get('mine'):
                            # Проигрыш на мине
                            row_data = res['row_data']
                            # Создаем клавиатуру с результатом
                            kb = []
                            row_buttons = []
                            for c in range(5):
                                row_buttons.append(InlineKeyboardButton(
                                    text=row_data['cells'][c], 
                                    callback_data="ignore"
                                ))
                            kb.append(row_buttons)
                            
                            await cb.message.edit_text(
                                f"💥 {cb.from_user.first_name}, БУМ! Вы наткнулись на мину!\n"
                                f"😞 Проигрыш: {bot_core.fmt(res['bet'])}",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                            )
                        else:
                            # Автоматический выигрыш на 9 этаже
                            await cb.message.edit_text(
                                f"🏆 {cb.from_user.first_name}, МАКСИМУМ! Вы достигли 9 этажа!\n\n"
                                f"💰 Выигрыш: +{bot_core.fmt(res['won'])}\n"
                                f"📈 Множитель: x{res['multiplier']:.1f}\n"
                                f"🎯 Этажей: {res['rows']}\n"
                                f"💵 Новый баланс: {bot_core.fmt(res['balance'])}"
                            )
                        return
                    
                    # Успешное открытие - автоматический переход
                    game = bot_core.tower.games.get(user_id)
                    if game:
                        kb = bot_core.tower.create_keyboard(user_id, game)
                        await cb.message.edit_text(
                            f"🏗️ {cb.from_user.first_name}, БАШНЯ | Этаж {game['current_row']+1}/9 | 💣 {game['mines_per_row']}\n"
                            f"💰 Ставка: {bot_core.fmt(game['bet'])}\n"
                            f"📈 x{game['current_multiplier']:.1f} | 💎 {bot_core.fmt(game['won'])}\n\n"
                            f"✅ Этаж {res['row']+1} пройден! Авто переход на этаж {game['current_row']+1}\n"
                            f"Выберите клетку:",
                            reply_markup=kb
                        )
                except Exception as e:
                    await cb.answer(f"❌ Ошибка: {e}")
        
        elif data.startswith('tower_cashout_'):
            parts = data.split('_')
            if len(parts) == 3:
                try:
                    user_id = int(parts[2])
                    if cb.from_user.id != user_id:
                        await cb.answer("❌ Это не ваша игра!", show_alert=True)
                        return
                    
                    res = bot_core.tower.cashout(user_id)
                    if not res['ok']:
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    
                    await cb.message.edit_text(
                        f"🏆 {cb.from_user.first_name}, ВЫ ЗАБРАЛИ ВЫИГРЫШ!\n\n"
                        f"💰 +{bot_core.fmt(res['won'])}\n"
                        f"📈 Множитель: x{res['multiplier']:.1f}\n"
                        f"🎯 Этажей пройдено: {res['rows']}\n"
                        f"💵 Новый баланс: {bot_core.fmt(res['balance'])}"
                    )
                except Exception as e:
                    await cb.answer(f"❌ Ошибка: {e}")
        
        # === СТАТУСЫ ===
        elif data.startswith('status_view_'):
            status_id = data[12:]
            statuses = bot_core.status_shop.get_all_statuses()
            status = statuses.get(status_id)
            if not status:
                await cb.answer("❌ Статус не найден", show_alert=True)
                return
            
            user = bot_core.db.get(cb.from_user.id)
            
            kb = []
            if user['status'] != status_id and user['balance'] >= status['price']:
                kb.append([InlineKeyboardButton(text="💳 Купить", callback_data=f"status_buy_{status_id}")])
            kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="status_back")])
            
            await cb.message.edit_text(
                f"{status['emoji']} **{status['name']}**\n\n"
                f"💰 Цена: {bot_core.fmt(status['price'])}\n"
                f"🎁 Бонус: {bot_core.fmt(status['min_bonus'])} - {bot_core.fmt(status['max_bonus'])} (каждый час)\n"
                f"⏰ Кулдаун: 1 час\n\n"
                f"📝 {status['description']}\n\n"
                f"💳 Ваш баланс: {bot_core.fmt(user['balance'])}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                parse_mode="Markdown"
            )
        
        elif data.startswith('status_buy_'):
            status_id = data[11:]
            res = bot_core.status_shop.buy_status(cb.from_user.id, status_id, bot_core.db)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await cmd_status_shop(cb.message)
        
        elif data == "status_back":
            await cmd_status_shop(cb.message)
        
        # === МАГАЗИН ===
        elif data.startswith('shop_view_'):
            id = data[10:]
            items = bot_core.shop.items()
            if id not in items:
                await cb.answer("❌ Товар не найден", show_alert=True)
                return
            item = items[id]
            user = bot_core.db.get(cb.from_user.id)
            kb = []
            if item.get('quantity', 0) > 0 and user['balance'] >= item.get('price', 0):
                kb.append([InlineKeyboardButton(text="💳 Купить", callback_data=f"shop_buy_{id}")])
            kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="shop_back")])
            await cb.message.edit_text(
                f"{item.get('emoji', '🎁')} {item.get('name', 'Товар')}\n"
                f"📝 {item.get('description', '')}\n"
                f"💰 {bot_core.fmt(item.get('price', 0))}\n"
                f"📦 {item.get('quantity', 0)} шт | 📊 {item.get('sold', 0)} продано\n"
                f"💳 Ваш баланс: {bot_core.fmt(user['balance'])}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )
        
        elif data.startswith('shop_buy_'):
            id = data[9:]
            res = bot_core.shop.buy(id, cb.from_user.id, bot_core.db)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await cmd_shop(cb.message)
        
        elif data == "shop_my_inv":
            await cmd_inventory(cb.message)
        
        elif data == "shop_back":
            await cmd_shop(cb.message)
        
        # === ИНВЕНТАРЬ ===
        elif data.startswith('inv_view_'):
            unique_id = data[9:]
            user_id = cb.from_user.id
            inv = bot_core.shop.inventory(user_id)
            item = None
            
            for i in inv:
                if i.get('unique_id') == unique_id:
                    item = i
                    break
            
            if not item:
                await cb.answer("❌ Предмет не найден!", show_alert=True)
                return
            
            kb = [
                [InlineKeyboardButton(text="🔄 Передать", callback_data=f"transfer_{unique_id}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="inv_back")]
            ]
            
            # Форматируем дату покупки
            purchased = item.get('purchased_at', '')
            if purchased:
                try:
                    purchased_date = datetime.datetime.fromisoformat(purchased).strftime("%d.%m.%Y %H:%M")
                except:
                    purchased_date = purchased[:10]
            else:
                purchased_date = "неизвестно"
            
            # Сокращаем текст, чтобы избежать MESSAGE_TOO_LONG
            unique_id_short = item.get('unique_id', '')[:15] + '...' if len(item.get('unique_id', '')) > 15 else item.get('unique_id', '')
            
            await cb.message.edit_text(
                f"**#{item.get('global_number', '?')} {item.get('emoji', '🎁')} {item.get('name', 'Предмет')}**\n\n"
                f"📝 {item.get('description', 'Нет описания')[:100]}{'...' if len(item.get('description', '')) > 100 else ''}\n"
                f"📅 Куплен: {purchased_date}\n"
                f"🔢 ID: `{unique_id_short}`",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                parse_mode="Markdown"
            )
        
        elif data == "inv_back":
            await cmd_inventory(cb.message)
        
        # === ПЕРЕДАЧА ===
        elif data.startswith('transfer_'):
            unique_id = data[9:]
            await state.update_data(transfer_unique_id=unique_id)
            await state.set_state(TransferStates.enter_username)
            await cb.message.edit_text(
                "🔄 Введите ID получателя:\n"
                "Пример: 123456789\n\n"
                "❌ Для отмены отправьте /cancel"
            )
        
        elif data == "ignore":
            pass
        
        await cb.answer()
        
    except Exception as e:
        # Логируем ошибку, но не показываем пользователю
        print(f"DEBUG: Error in callback_handler: {e}")
        await cb.answer()

# === FSM ОБРАБОТЧИКИ ===
async def handle_transfer_id(msg: Message, state: FSMContext):
    """Обработка ввода ID для передачи"""
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.answer("❌ Передача отменена")
        return
    
    data = await state.get_data()
    unique_id = data.get('transfer_unique_id')
    
    if not unique_id:
        await state.clear()
        await msg.answer("❌ Ошибка, попробуйте снова")
        return
    
    try:
        recipient_id = int(msg.text.strip())
    except:
        await msg.answer("❌ Неверный ID! Введите число")
        return
    
    if recipient_id == msg.from_user.id:
        await msg.answer("❌ Нельзя передать предмет самому себе!")
        return
    
    # Получаем предмет из инвентаря
    item, owner_id = bot_core.shop.get_item_by_unique_id(unique_id)
    
    if not item or owner_id != msg.from_user.id:
        await state.clear()
        await msg.answer("❌ Предмет не найден в вашем инвентаре")
        return
    
    # Удаляем у отправителя
    bot_core.shop.remove_from_inventory(msg.from_user.id, unique_id)
    
    # Добавляем получателю
    bot_core.shop.add_to_inventory(recipient_id, item)
    
    await state.clear()
    await msg.answer(
        f"✅ Предмет передан!\n\n"
        f"#{item['global_number']} {item['emoji']} {item['name']}\n"
        f"📤 Получатель: ID {recipient_id}"
    )
    
    # Уведомляем получателя
    try:
        await msg.bot.send_message(
            recipient_id,
            f"🎁 Вам передали NFT!\n\n"
            f"#{item['global_number']} {item['emoji']} {item['name']}\n"
            f"📤 Отправитель: {msg.from_user.full_name}"
        )
    except:
        pass

async def handle_loan_payment(msg: Message, state: FSMContext):
    """Обработка оплаты кредита"""
    if msg.text.lower() == '/cancel':
        await state.clear()
        await msg.answer("❌ Оплата отменена")
        return
    
    data = await state.get_data()
    loan_id = data.get('pay_loan_id')
    
    if not loan_id:
        await state.clear()
        await msg.answer("❌ Ошибка, попробуйте снова")
        return
    
    user_id = msg.from_user.id
    user = bot_core.db.get(user_id)
    amount = bot_core.parse_bet(msg.text, user['balance'])
    
    if amount <= 0:
        await msg.answer("❌ Неверная сумма!")
        return
    
    res = bot_core.bank.pay_loan(user_id, loan_id, amount, user['balance'])
    
    if res['ok']:
        # Списываем с основного счета
        new_balance = user['balance'] - amount
        bot_core.db.update(user_id, balance=new_balance)
        await msg.answer(res['msg'])
        await state.clear()
        
        # Показываем обновленный список кредитов
        await cmd_loan_list(msg)
    else:
        await msg.answer(res['msg'])

# === РУССКИЕ КОМАНДЫ ===
async def handle_russian(msg: Message, state: FSMContext):
    text = msg.text.lower().strip()
    
    if text in ['баланс', 'б']:
        await cmd_balance(msg)
    elif text in ['профиль', 'проф']:
        await cmd_full_profile(msg)
    elif text == 'п':
        await cmd_short_profile(msg)
    elif text == 'топ':
        await cmd_top_balance(msg)
    elif text == 'топ статусы':
        await cmd_top_status(msg)
    elif text in ['помощь', 'help', 'команды']:
        await cmd_help(msg)
    elif text == 'банк':
        await cmd_bank(msg, state)
    elif text == 'карта':
        await cmd_card_balance(msg)
    elif text.startswith('положить '):
        parts = text.split()
        if len(parts) == 2:
            class FakeCommand:
                def __init__(self, args):
                    self.args = parts[1]
            await cmd_card_deposit(msg, FakeCommand(parts[1]), state)
        else:
            await msg.answer("Использование: положить [сумма]")
    elif text.startswith('снять '):
        parts = text.split()
        if len(parts) == 2:
            class FakeCommand:
                def __init__(self, args):
                    self.args = parts[1]
            await cmd_card_withdraw(msg, FakeCommand(parts[1]), state)
        else:
            await msg.answer("Использование: снять [сумма]")
    elif text.startswith('вклад '):
        parts = text.split()
        if len(parts) == 3:
            class FakeCommand:
                def __init__(self, args):
                    self.args = f"{parts[1]} {parts[2]}"
            await cmd_deposit_create(msg, FakeCommand(f"{parts[1]} {parts[2]}"), state)
        else:
            await msg.answer("Использование: вклад [сумма] [дни]")
    elif text == 'вклады':
        await cmd_deposit_list(msg)
    elif text.startswith('кредит '):
        parts = text.split()
        if len(parts) == 3:
            class FakeCommand:
                def __init__(self, args):
                    self.args = f"{parts[1]} {parts[2]}"
            await cmd_loan_create(msg, FakeCommand(f"{parts[1]} {parts[2]}"), state)
        else:
            await msg.answer("Использование: кредит [сумма] [дни]")
    elif text == 'кредиты':
        await cmd_loan_list(msg)
    elif text == 'статусы':
        await cmd_status_shop(msg)
    elif text == 'статус':
        await cmd_my_status(msg)
    elif text == 'бонус':
        await cmd_bonus(msg)
    elif text == 'магазин':
        await cmd_shop(msg)
    elif text in ['инвентарь', 'мои нфт']:
        await cmd_inventory(msg)
    elif text.startswith('промо '):
        code = text[6:].strip().upper()
        res = bot_core.promo.use(code, msg.from_user.id, bot_core.db)
        await msg.answer(res['msg'])
    elif text.startswith('дать ') or text.startswith('дай '):
        await cmd_give(msg)
    elif text.startswith('краш'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_crash(msg, FakeCommand(args))
        else:
            await cmd_crash(msg, FakeCommand(None))
    elif text.startswith('монетка'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_coin(msg, FakeCommand(args))
        else:
            await cmd_coin(msg, FakeCommand(None))
    elif text.startswith('слоты'):
        parts = text.split()
        if len(parts) >= 2:
            class FakeCommand:
                def __init__(self, args):
                    self.args = parts[1]
            await cmd_slots(msg, FakeCommand(parts[1]))
        else:
            await cmd_slots(msg, FakeCommand(None))
    elif text.startswith('кубик'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_dice(msg, FakeCommand(args))
        else:
            await cmd_dice(msg, FakeCommand(None))
    elif text.startswith('мины'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_mines(msg, FakeCommand(args))
        else:
            await cmd_mines(msg, FakeCommand(None))
    elif text.startswith('башня'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_tower(msg, FakeCommand(args))
        else:
            await cmd_tower(msg, FakeCommand(None))
    elif text.startswith('рулетка') or text.startswith('рул'):
        parts = text.split()
        if len(parts) >= 2:
            args = ' '.join(parts[1:])
            class FakeCommand:
                def __init__(self, args):
                    self.args = args
            await cmd_roulette(msg, FakeCommand(args))
        else:
            await cmd_roulette(msg, FakeCommand(None))

# === АДМИН ===
async def admin_promo_list(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    promos = bot_core.promo.all()
    if not promos:
        await msg.answer("📭 Нет промокодов")
        return
    text = "📋 ПРОМОКОДЫ:\n"
    for code, p in promos.items():
        try:
            days = (datetime.datetime.fromisoformat(p['expires']) - datetime.datetime.now()).days
            text += f"\n🎫 {code}\n💰 {bot_core.fmt(p['reward'])} | 🎯 {p['used']}/{p['limit']}\n⏰ {days} дн.\n"
        except:
            text += f"\n🎫 {code} (ошибка в данных)\n"
    await msg.answer(text)

async def admin_shop_list(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    items = bot_core.shop.items()
    if not items:
        await msg.answer("🛍️ Магазин пуст")
        return
    text = "🛍️ ТОВАРЫ:\n"
    for id, item in items.items():
        text += f"\n{item.get('emoji', '🎁')} {item.get('name', 'Товар')} (ID: {id})\n"
        text += f"💰 {bot_core.fmt(item.get('price', 0))} | 📦 {item.get('quantity', 0)} | 📊 {item.get('sold', 0)}\n"
    await msg.answer(text)

async def admin_counters(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    counters = bot_core.counters.get_all_counters()
    text = "📊 СЧЕТЧИКИ NFT:\n"
    for item_id, count in counters.items():
        text += f"• {item_id}: {count} экземпляров\n"
    await msg.answer(text)

async def admin_users_list(msg: Message):
    """Админ-команда для просмотра всех пользователей"""
    if msg.from_user.id != ADMIN_ID:
        return
    
    data = bot_core.db.get_all_users_data()
    total_users = len(data)
    
    # Подсчет активных пользователей (с балансом > START_BALANCE или игравших)
    active_users = 0
    for uid, user in data.items():
        if user.get('games_played', 0) > 0 or user.get('balance', 0) > START_BALANCE:
            active_users += 1
    
    text = f"📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ:\n"
    text += f"👥 Всего в базе: {total_users}\n"
    text += f"🎮 Активных: {active_users}\n"
    text += f"💤 Неактивных: {total_users - active_users}\n\n"
    text += f"📋 Список ID (первые 20):\n"
    
    for i, uid in enumerate(sorted(data.keys())[:20]):
        user = data[uid]
        statuses = bot_core.status_shop.get_all_statuses()
        status = statuses.get(user.get('status', 'novice'), statuses['novice'])
        text += f"{i+1}. {uid}: {status['emoji']} {bot_core.fmt(user.get('balance', 0))} | 🎮 {user.get('games_played', 0)}\n"
    
    if len(data) > 20:
        text += f"...и еще {len(data) - 20}\n"
    
    await msg.answer(text)

async def admin_create_promo(msg: Message, command: CommandObject):
    """Создать промокод (админ)"""
    if msg.from_user.id != ADMIN_ID:
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 2:
        await msg.answer("Использование: /admin_create_promo КОД НАГРАДА [ЛИМИТ=100] [ДНИ=30]")
        return
    
    code = args[0].upper()
    reward = bot_core.parse_bet(args[1])
    limit = int(args[2]) if len(args) > 2 else 100
    days = int(args[3]) if len(args) > 3 else 30
    
    success = bot_core.promo.create(code, reward, limit, days)
    if success:
        await msg.answer(f"✅ Промокод {code} создан!\nНаграда: {bot_core.fmt(reward)}\nЛимит: {limit}\nДней: {days}")
    else:
        await msg.answer("❌ Промокод уже существует!")

async def admin_check_inventory(msg: Message):
    """Админ-команда для проверки инвентаря пользователя"""
    if msg.from_user.id != ADMIN_ID:
        return
    
    args = msg.text.split()
    if len(args) != 2:
        await msg.answer("Использование: /check_inv [user_id]")
        return
    
    try:
        user_id = int(args[1])
        inv = bot_core.shop.inventory(user_id)
        
        text = f"📦 **Инвентарь пользователя {user_id}**\n\n"
        text += f"Всего предметов: {len(inv)}\n\n"
        
        if inv:
            for i, item in enumerate(inv, 1):
                text += f"{i}. #{item.get('global_number')} {item.get('emoji')} {item.get('name')}\n"
                text += f"   ID: `{item.get('unique_id', '')[:20]}...`\n"
        else:
            text += "Инвентарь пуст"
        
        await msg.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

# === ЗАПУСК ===
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Команды со слэшем
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_balance, Command("balance"))
    dp.message.register(cmd_full_profile, Command("profile"))
    dp.message.register(cmd_short_profile, Command("p"))
    dp.message.register(cmd_top_balance, Command("top"))
    dp.message.register(cmd_top_status, Command("top_status"))
    dp.message.register(cmd_help, Command("help"))
    
    # Банк
    dp.message.register(cmd_bank, Command("bank"))
    dp.message.register(cmd_card_balance, Command("card"))
    dp.message.register(cmd_card_deposit, Command("deposit"))
    dp.message.register(cmd_card_withdraw, Command("withdraw"))
    dp.message.register(cmd_deposit_create, Command("deposit_create"))
    dp.message.register(cmd_deposit_list, Command("deposits"))
    dp.message.register(cmd_loan_create, Command("loan"))
    dp.message.register(cmd_loan_list, Command("loans"))
    
    # Статусы
    dp.message.register(cmd_status_shop, Command("statuses"))
    dp.message.register(cmd_my_status, Command("status"))
    dp.message.register(cmd_bonus, Command("bonus"))
    
    # NFT
    dp.message.register(cmd_shop, Command("shop"))
    dp.message.register(cmd_inventory, Command("inventory"))
    dp.message.register(cmd_promo, Command("promo"))
    dp.message.register(cmd_transfer, Command("transfer"))
    
    # Игры
    dp.message.register(cmd_coin, Command("coinflip"))
    dp.message.register(cmd_slots, Command("slots"))
    dp.message.register(cmd_dice, Command("dice"))
    dp.message.register(cmd_crash, Command("crash"))
    dp.message.register(cmd_mines, Command("mines"))
    dp.message.register(cmd_tower, Command("tower"))
    dp.message.register(cmd_roulette, Command("roulette"))
    
    # Команда "дать"
    dp.message.register(cmd_give, Command("give"))
    
    # Админ команды
    dp.message.register(admin_promo_list, Command("admin_promo_list"))
    dp.message.register(admin_shop_list, Command("admin_shop_list"))
    dp.message.register(admin_counters, Command("admin_counters"))
    dp.message.register(admin_users_list, Command("admin_users"))
    dp.message.register(admin_create_promo, Command("admin_create_promo"))
    dp.message.register(admin_check_inventory, Command("check_inv"))
    
    # FSM обработчики
    dp.message.register(handle_transfer_id, TransferStates.enter_username)
    dp.message.register(handle_loan_payment, BankStates.waiting_loan_payment)
    
    # Русские команды
    dp.message.register(handle_russian, F.text)
    
    # Callback
    dp.callback_query.register(callback_handler)
    
    print("✅ Бот запущен!")
    print(f"✅ Токен: {BOT_TOKEN[:10]}...")
    print(f"✅ Стартовый баланс: {START_BALANCE} коинов")
    print("✅ Добавлен БАНК:")
    print("   • 💳 Карта (скрытый счет)")
    print("   • 📈 Вклады (пассивный доход)")
    print("   • 📉 Кредиты (с рейтингом)")
    print("✅ Новые игры: БАШНЯ и РУЛЕТКА")
    print("✅ Башня: ряды сохраняются, авто переход")
    print("✅ Система статусов и бонусов")
    print("✅ ИСПРАВЛЕН ИНВЕНТАРЬ и МАГАЗИН")
    print("✅ Добавлена отладка (смотрите консоль)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Бот остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
