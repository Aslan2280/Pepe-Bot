import json, os, random, logging, asyncio, re, datetime, string
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8474641060:AAH4cRqRcBFhvEaQowd0jG8WQtPDTffzN0w"
CREATOR_ID = 6539341659  # ID создателя
DATABASE_FILE = "casino_data.json"
PROMO_FILE = "promo_codes.json"
SHOP_FILE = "shop_items.json"
INVENTORY_FILE = "inventory.json"
COUNTERS_FILE = "counters.json"
STATUS_SHOP_FILE = "status_shop.json"
BANK_DATA_FILE = "bank_data.json"
BANK_SETTINGS_FILE = "bank_settings.json"
MARKET_FILE = "market.json"
BANNED_USERS_FILE = "banned_users.json"
ADMINS_FILE = "admins.json"
ADMIN_LOGS_FILE = "admin_logs.json"
START_BALANCE = 10000

# Настройки промокодов
MIN_PROMO_REWARD = 1000
MAX_PROMO_REWARD = 10000000
MIN_PROMO_LIMIT = 1
MAX_PROMO_LIMIT = 50
PROMO_DAYS_VALID = 7
PROMO_CODE_LENGTH = 8

logging.basicConfig(level=logging.INFO)

# === СОСТОЯНИЯ ===
class TransferStates(StatesGroup):
    enter_username = State()
    confirm = State()

class TransferNFTStates(StatesGroup):
    waiting_user = State()
    waiting_nft = State()
    waiting_confirm = State()

class BankStates(StatesGroup):
    waiting_deposit_amount = State()
    waiting_deposit_days = State()
    waiting_loan_amount = State()
    waiting_loan_days = State()
    waiting_card_amount = State()
    waiting_loan_payment = State()

class PromoStates(StatesGroup):
    waiting_reward = State()
    waiting_limit = State()

class MarketStates(StatesGroup):
    waiting_price = State()

class AdminStates(StatesGroup):
    waiting_nft_id = State()
    waiting_nft_name = State()
    waiting_nft_price = State()
    waiting_nft_quantity = State()
    waiting_nft_description = State()
    waiting_nft_emoji = State()
    waiting_status_name = State()
    waiting_ban_reason = State()

# === УПРОЩЕННАЯ БД ===
class DB:
    def __init__(self, file): 
        self.file = file
        self._ensure()
    def _ensure(self):
        if not os.path.exists(self.file):
            with open(self.file, 'w', encoding='utf-8') as f: 
                json.dump({}, f, ensure_ascii=False, indent=2)
    def read(self):
        try:
            with open(self.file, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except:
            return {}
    def write(self, data):
        with open(self.file, 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=2, ensure_ascii=False)

# === СЧЕТЧИКИ ===
class CountersDB:
    def __init__(self): 
        self.db = DB(COUNTERS_FILE)
    def get_next(self, item_id):
        data = self.db.read()
        data.setdefault('item_counters', {})
        data['item_counters'][item_id] = data['item_counters'].get(item_id, 0) + 1
        self.db.write(data)
        return data['item_counters'][item_id]

# === БАН ПОЛЬЗОВАТЕЛЕЙ ===
class BanDB:
    def __init__(self):
        self.db = DB(BANNED_USERS_FILE)
    
    def is_banned(self, uid):
        data = self.db.read()
        return str(uid) in data
    
    def ban(self, uid, admin_id, reason=""):
        data = self.db.read()
        uid = str(uid)
        data[uid] = {
            'banned_at': datetime.datetime.now().isoformat(),
            'banned_by': admin_id,
            'reason': reason if reason else "Не указана"
        }
        self.db.write(data)
        return True
    
    def unban(self, uid):
        data = self.db.read()
        uid = str(uid)
        if uid in data:
            del data[uid]
            self.db.write(data)
            return True
        return False
    
    def get_ban_info(self, uid):
        data = self.db.read()
        return data.get(str(uid))

# === АДМИНЫ ===
class AdminDB:
    def __init__(self):
        self.db = DB(ADMINS_FILE)
        self._ensure_creator()
    
    def _ensure_creator(self):
        """Убеждаемся, что создатель есть в списке"""
        data = self.db.read()
        if str(CREATOR_ID) not in data:
            data[str(CREATOR_ID)] = {
                "is_creator": True,
                "added_by": None,
                "added_at": datetime.datetime.now().isoformat()
            }
            self.db.write(data)
    
    def is_admin(self, uid):
        """Проверяет, является ли пользователь админом"""
        data = self.db.read()
        return str(uid) in data
    
    def is_creator(self, uid):
        """Проверяет, является ли пользователь создателем"""
        data = self.db.read()
        admin = data.get(str(uid))
        return admin and admin.get("is_creator", False)
    
    def get_all_admins(self):
        """Возвращает список всех админов"""
        return self.db.read()
    
    def add_admin(self, uid, added_by):
        """Добавляет обычного админа"""
        if self.is_admin(uid):
            return {'ok': False, 'msg': '❌ Пользователь уже админ!'}
        
        data = self.db.read()
        data[str(uid)] = {
            "is_creator": False,
            "added_by": added_by,
            "added_at": datetime.datetime.now().isoformat()
        }
        self.db.write(data)
        return {'ok': True, 'msg': f'✅ Пользователь {uid} назначен админом'}
    
    def remove_admin(self, uid, removed_by):
        """Удаляет админа"""
        if not self.is_admin(uid):
            return {'ok': False, 'msg': '❌ Пользователь не админ!'}
        
        if self.is_creator(uid):
            return {'ok': False, 'msg': '❌ Нельзя удалить создателя!'}
        
        data = self.db.read()
        del data[str(uid)]
        self.db.write(data)
        return {'ok': True, 'msg': f'✅ Пользователь {uid} снят с админки'}
    
    def get_admin_info(self, uid):
        """Возвращает информацию об админе"""
        return self.db.read().get(str(uid))

# === ЛОГИ АДМИНОВ ===
class AdminLogs:
    def __init__(self):
        self.db = DB(ADMIN_LOGS_FILE)
        self._ensure()
    
    def _ensure(self):
        """Убеждаемся, что структура существует"""
        data = self.db.read()
        if not data or "logs" not in data:
            data = {"logs": []}
            self.db.write(data)
    
    def add_log(self, admin_id, action, target_id=None, amount=None, details=""):
        """Добавляет запись в лог"""
        data = self.db.read()
        
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "admin_id": admin_id,
            "action": action,
            "target_id": target_id,
            "amount": amount,
            "details": details
        }
        
        data["logs"].append(log_entry)
        self.db.write(data)
        return log_entry
    
    def get_logs(self, limit=50, admin_id=None, action=None):
        """Получает логи с фильтрацией"""
        data = self.db.read()
        logs = data.get("logs", [])
        
        if admin_id:
            logs = [log for log in logs if log.get("admin_id") == admin_id]
        if action:
            logs = [log for log in logs if log.get("action") == action]
        
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return logs[:limit]
    
    def clear_logs(self):
        """Очищает все логи"""
        data = {"logs": []}
        self.db.write(data)
        return True
    
    def get_stats(self):
        """Возвращает статистику по действиям"""
        data = self.db.read()
        logs = data.get("logs", [])
        
        stats = {
            "total_actions": len(logs),
            "by_action": {},
            "by_admin": {},
            "total_given": 0,
            "total_taken": 0,
            "total_bans": 0,
            "last_24h": 0
        }
        
        now = datetime.datetime.now()
        day_ago = now - datetime.timedelta(days=1)
        
        for log in logs:
            action = log.get("action", "unknown")
            admin = str(log.get("admin_id", "unknown"))
            amount = log.get("amount", 0) or 0
            
            stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
            stats["by_admin"][admin] = stats["by_admin"].get(admin, 0) + 1
            
            if action == "give":
                stats["total_given"] += amount
            elif action == "take":
                stats["total_taken"] += amount
            elif action == "ban":
                stats["total_bans"] += 1
            
            try:
                log_time = datetime.datetime.fromisoformat(log.get("timestamp", ""))
                if log_time > day_ago:
                    stats["last_24h"] += 1
            except:
                pass
        
        return stats
    
    def format_logs(self, logs, detailed=False):
        """Форматирует логи для вывода"""
        if not logs:
            return "📭 Логов пока нет"
        
        text = "📋 **ПОСЛЕДНИЕ ДЕЙСТВИЯ АДМИНОВ**\n\n"
        
        for log in logs[:10]:
            timestamp = log.get("timestamp", "Unknown")[:16].replace("T", " ")
            admin_id = log.get("admin_id", "?")
            action = log.get("action", "?")
            target = log.get("target_id", "—")
            amount = log.get("amount")
            details = log.get("details", "")
            
            action_emoji = {
                "give": "💰", "take": "💸", "ban": "⛔", "unban": "✅",
                "make_admin": "👑", "remove_admin": "👤", "create_promo": "🎫",
                "give_status": "⭐", "create_nft": "🖼️", "clear_logs": "🧹"
            }.get(action, "🔹")
            
            amount_str = f" | {fmt(amount)}" if amount else ""
            target_str = f" | {target}" if target != "—" else ""
            details_str = f"\n      📝 {details}" if details else ""
            
            text += f"{action_emoji} **{action.upper()}**{amount_str}{target_str}\n"
            text += f"   🕐 {timestamp} | 👤 Админ: {admin_id}{details_str}\n\n"
        
        if detailed and len(logs) > 10:
            text += f"*... и еще {len(logs) - 10} записей*"
        
        return text

# === ПОЛЬЗОВАТЕЛИ ===
class UserDB:
    def __init__(self): 
        self.db = DB(DATABASE_FILE)
    
    def get(self, uid):
        data = self.db.read()
        uid = str(uid)
        if uid not in data:
            data[uid] = {'balance': START_BALANCE, 'games_played': 0, 'wins': 0, 
                        'used_promocodes': [], 'created_promocodes': [], 'status': 'novice',
                        'last_bonus': None, 'bonus_history': []}
            self.db.write(data)
            return data[uid]
        return data[uid]
    
    def update(self, uid, **kwargs):
        data = self.db.read()
        uid = str(uid)
        if uid not in data: 
            data[uid] = self.get(uid)
        data[uid].update(kwargs)
        self.db.write(data)
    
    def top(self, limit=10):
        """Топ пользователей по балансу (без админов)"""
        data = self.db.read()
        users = []
        for uid, u in data.items():
            if is_admin(int(uid)):
                continue
            users.append((uid, u))
        return sorted(users, key=lambda x: x[1].get('balance', 0), reverse=True)[:limit]
    
    def top_by_status(self):
        """Топ пользователей по статусам (без админов)"""
        data = self.db.read()
        status_groups = {}
        for uid, u in data.items():
            if is_admin(int(uid)):
                continue
            status = u.get('status', 'novice')
            if status not in status_groups: 
                status_groups[status] = []
            status_groups[status].append((uid, u))
        
        for status in status_groups:
            status_groups[status].sort(key=lambda x: x[1].get('balance', 0), reverse=True)
        return status_groups
    
    def get_total_balance(self, uid):
        """Возвращает общий баланс (наличные + карта)"""
        user = self.get(uid)
        bank_data = core.bank.get(uid)
        total = user['balance'] + bank_data['card_balance']
        return total
    
    def get_all_users_total_balance(self):
        """Возвращает список всех пользователей с их общим балансом (без админов)"""
        data = self.db.read()
        result = []
        for uid, user in data.items():
            if is_admin(int(uid)):
                continue
            bank_data = core.bank.get(uid)
            total = user['balance'] + bank_data['card_balance']
            result.append((uid, total, user['balance'], bank_data['card_balance']))
        return sorted(result, key=lambda x: x[1], reverse=True)

# === СТАТУСЫ ===
class StatusShop:
    def __init__(self):
        self.db = DB(STATUS_SHOP_FILE)
        if not self.db.read():
            self.db.write({
                "novice": {"name": "Новичок", "emoji": "🌱", "price": 0, "min_bonus": 500, "max_bonus": 2500, "description": "Начальный статус для всех новичков"},
                "player": {"name": "Игрок", "emoji": "🎮", "price": 50000, "min_bonus": 2500, "max_bonus": 10000, "description": "Уже кое-что понимаешь в играх"},
                "gambler": {"name": "Азартный", "emoji": "🎲", "price": 250000, "min_bonus": 10000, "max_bonus": 50000, "description": "Риск — твоё второе имя"},
                "vip": {"name": "VIP", "emoji": "💎", "price": 1000000, "min_bonus": 50000, "max_bonus": 250000, "description": "Особый статус для особых игроков"},
                "legend": {"name": "Легенда", "emoji": "👑", "price": 5000000, "min_bonus": 250000, "max_bonus": 1000000, "description": "Легенда казино, сам Бог удачи"},
                "oligarch": {"name": "Олигарх", "emoji": "💰", "price": 25000000, "min_bonus": 1000000, "max_bonus": 5000000, "description": "У тебя больше денег, чем у некоторых стран"},
                "immortal": {"name": "Бессмертный", "emoji": "⚡", "price": 100000000, "min_bonus": 5000000, "max_bonus": 25000000, "description": "Ты достиг просветления"}
            })
    
    def all(self): 
        return self.db.read()
    
    def get_status(self, status_id):
        return self.db.read().get(status_id)
    
    def get_status_by_name(self, name):
        statuses = self.all()
        name_lower = name.lower()
        for status_id, status in statuses.items():
            if status['name'].lower() == name_lower:
                return status_id, status
        return None, None
    
    def buy(self, uid, status_id, user_db):
        statuses = self.all()
        if status_id not in statuses: 
            return {'ok': False, 'msg': '❌ Статус не найден!'}
        s = statuses[status_id]
        user = user_db.get(uid)
        if user['status'] == status_id: 
            return {'ok': False, 'msg': '❌ У вас уже есть этот статус!'}
        if user['balance'] < s['price']: 
            return {'ok': False, 'msg': f'❌ Нужно: {fmt(s["price"])}'}
        user_db.update(uid, balance=user['balance'] - s['price'], status=status_id)
        return {'ok': True, 'msg': f'✅ Куплен статус {s["emoji"]} {s["name"]}!'}
    
    def admin_give_status(self, uid, status_id, user_db):
        statuses = self.all()
        if status_id not in statuses: 
            return {'ok': False, 'msg': '❌ Статус не найден!'}
        s = statuses[status_id]
        user = user_db.get(uid)
        user_db.update(uid, status=status_id)
        return {'ok': True, 'msg': f'✅ Админ выдал статус {s["emoji"]} {s["name"]}!'}
    
    def get_bonus(self, uid, user_db):
        user = user_db.get(uid)
        statuses = self.all()
        status = statuses.get(user['status'], statuses['novice'])
        
        last_bonus = user.get('last_bonus')
        if last_bonus:
            try:
                last_time = datetime.datetime.fromisoformat(last_bonus)
                hours_passed = (datetime.datetime.now() - last_time).total_seconds() / 3600
                if hours_passed < 1:
                    next_bonus = int((1 - hours_passed) * 60)
                    return {'ok': False, 'msg': f'⏰ Бонус еще не доступен!\nСледующий бонус через {next_bonus} минут.'}
            except:
                pass
        
        bonus = random.randint(status['min_bonus'], status['max_bonus'])
        new_balance = user['balance'] + bonus
        
        user['last_bonus'] = datetime.datetime.now().isoformat()
        user['bonus_history'] = user.get('bonus_history', []) + [{'amount': bonus, 'time': datetime.datetime.now().isoformat()}]
        user_db.update(uid, balance=new_balance, last_bonus=user['last_bonus'], bonus_history=user['bonus_history'])
        
        return {
            'ok': True,
            'msg': f'🎁 **ЕЖЕЧАСНЫЙ БОНУС**\n\nВаш статус: {status["emoji"]} {status["name"]}\nВы получили: +{fmt(bonus)}\n\n💰 Новый баланс: {fmt(new_balance)}'
        }

# === ПРОМОКОДЫ ===
class PromoDB:
    def __init__(self): 
        self.db = DB(PROMO_FILE)
    
    def gen_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(PROMO_CODE_LENGTH))
            if code not in self.db.read(): 
                return code
    
    def create(self, reward, creator_id, limit=10):
        if reward < MIN_PROMO_REWARD: 
            return {'ok': False, 'msg': f'❌ Мин награда: {fmt(MIN_PROMO_REWARD)}'}
        if reward > MAX_PROMO_REWARD: 
            return {'ok': False, 'msg': f'❌ Макс награда: {fmt(MAX_PROMO_REWARD)}'}
        if limit < MIN_PROMO_LIMIT: 
            return {'ok': False, 'msg': f'❌ Мин лимит: {MIN_PROMO_LIMIT}'}
        if limit > MAX_PROMO_LIMIT: 
            return {'ok': False, 'msg': f'❌ Макс лимит: {MAX_PROMO_LIMIT}'}
        
        code = self.gen_code()
        promos = self.db.read()
        promos[code] = {
            'reward': reward, 'limit': limit, 'used': 0,
            'expires': (datetime.datetime.now() + datetime.timedelta(days=PROMO_DAYS_VALID)).isoformat(),
            'users': [], 'creator': creator_id, 'created_at': datetime.datetime.now().isoformat()
        }
        self.db.write(promos)
        return {'ok': True, 'code': code}
    
    def use(self, code, uid, user_db):
        promos = self.db.read()
        if code not in promos: 
            return {'ok': False, 'msg': '❌ Промокод не найден!'}
        p = promos[code]
        if p.get('creator') == uid: 
            return {'ok': False, 'msg': '❌ Нельзя использовать свой промокод!'}
        if datetime.datetime.now() > datetime.datetime.fromisoformat(p['expires']): 
            return {'ok': False, 'msg': '❌ Просрочен!'}
        if p['used'] >= p['limit']: 
            return {'ok': False, 'msg': '❌ Лимит исчерпан!'}
        if uid in p['users']: 
            return {'ok': False, 'msg': '❌ Уже использовали!'}
        
        user = user_db.get(uid)
        user_db.update(uid, balance=user['balance'] + p['reward'], used_promocodes=user['used_promocodes'] + [code])
        p['used'] += 1
        p['users'].append(uid)
        self.db.write(promos)
        return {'ok': True, 'msg': f'🎉 Получено: {fmt(p["reward"])}'}
    
    def my_promos(self, creator_id):
        promos = self.db.read()
        result = []
        total_used = total_claimed = 0
        for code, p in promos.items():
            if p.get('creator') == creator_id:
                p['code'] = code
                p['remaining'] = p['limit'] - p['used']
                p['claimed'] = p['used'] * p['reward']
                total_used += p['used']
                total_claimed += p['claimed']
                result.append(p)
        return result, total_used, total_claimed

# === МАГАЗИН NFT ===
class ShopDB:
    def __init__(self):
        self.shop = DB(SHOP_FILE)
        self.inv = DB(INVENTORY_FILE)
        self.counters = CountersDB()
    
    def add(self, id, name, price, qty, desc="", emoji="🎁"):
        items = self.shop.read()
        if id in items: 
            return False
        items[id] = {'name': name, 'price': price, 'quantity': qty, 'sold': 0, 'description': desc, 'emoji': emoji}
        self.shop.write(items)
        return True
    
    def buy(self, id, uid, user_db):
        items = self.shop.read()
        if id not in items: 
            return {'ok': False, 'msg': '❌ Товар не найден!'}
        item = items[id]
        user = user_db.get(uid)
        if item['quantity'] <= 0: 
            return {'ok': False, 'msg': '❌ Нет в наличии!'}
        if user['balance'] < item['price']: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        num = self.counters.get_next(id)
        user_db.update(uid, balance=user['balance'] - item['price'])
        item['quantity'] -= 1
        item['sold'] += 1
        self.shop.write(items)
        
        inv = self.inv.read()
        inv.setdefault(str(uid), []).append({
            'item_id': id, 'global_number': num, 'name': item['name'], 'emoji': item['emoji'],
            'description': item['description'], 'purchased_at': datetime.datetime.now().isoformat(),
            'unique_id': f"{uid}_{id}_{num}_{random.randint(1000,9999)}",
            'is_upgraded': False
        })
        self.inv.write(inv)
        return {'ok': True, 'msg': f'🎉 Куплено {item["emoji"]} {item["name"]} #{num}'}
    
    def items(self): 
        return self.shop.read()
    
    def inventory(self, uid): 
        return self.inv.read().get(str(uid), [])
    
    def transfer_nft(self, from_uid, to_uid, unique_id):
        inv_data = self.inv.read()
        from_inv = inv_data.get(str(from_uid), [])
        to_inv = inv_data.get(str(to_uid), [])
        
        nft_index = None
        nft = None
        for i, item in enumerate(from_inv):
            if item['unique_id'] == unique_id:
                nft_index = i
                nft = item.copy()
                break
        
        if nft_index is None:
            return {'ok': False, 'msg': '❌ NFT не найден!'}
        
        from_inv.pop(nft_index)
        nft['unique_id'] = f"{to_uid}_{nft['item_id']}_{nft.get('global_number', 0)}_{random.randint(1000,9999)}"
        nft['purchased_at'] = datetime.datetime.now().isoformat()
        nft['transferred_at'] = datetime.datetime.now().isoformat()
        to_inv.append(nft)
        
        inv_data[str(from_uid)] = from_inv
        inv_data[str(to_uid)] = to_inv
        self.inv.write(inv_data)
        
        return {'ok': True, 'msg': f'✅ NFT передан!', 'nft': nft}

# === РЫНОК ===
class Market:
    def __init__(self):
        self.db = DB(MARKET_FILE)
        self._ensure()
    
    def _ensure(self):
        data = self.db.read()
        if not data or 'market_counter' not in data:
            data = {
                "market_counter": 0,
                "listings": []
            }
            self.db.write(data)
    
    def get_next_id(self):
        data = self.db.read()
        current = data.get("market_counter", 0)
        new_id = current + 1
        data["market_counter"] = new_id
        self.db.write(data)
        return new_id
    
    def add_listing(self, seller_id, nft, price):
        if price <= 0:
            return {'ok': False, 'msg': '❌ Цена должна быть положительной!'}
        
        data = self.db.read()
        listing_id = self.get_next_id()
        
        inv_data = core.shop.inv.read()
        seller_inv = inv_data.get(str(seller_id), [])
        
        found = False
        for i, item in enumerate(seller_inv):
            if item['unique_id'] == nft['unique_id']:
                seller_inv.pop(i)
                found = True
                break
        
        if not found:
            return {'ok': False, 'msg': '❌ NFT не найден в инвентаре!'}
        
        inv_data[str(seller_id)] = seller_inv
        core.shop.inv.write(inv_data)
        
        listing_nft = nft.copy()
        listing_nft.pop('unique_id', None)
        
        listing = {
            'id': listing_id,
            'seller_id': seller_id,
            'nft': listing_nft,
            'price': price,
            'listed_at': datetime.datetime.now().isoformat(),
            'status': 'active'
        }
        
        data['listings'].append(listing)
        self.db.write(data)
        
        return {'ok': True, 'msg': f'✅ NFT выставлен на рынок за {fmt(price)}', 'listing_id': listing_id}
    
    def get_listings(self, page=0, per_page=5):
        data = self.db.read()
        active_listings = [l for l in data['listings'] if l.get('status') == 'active']
        start = page * per_page
        end = start + per_page
        return active_listings[start:end], len(active_listings)
    
    def get_listing(self, listing_id):
        data = self.db.read()
        for listing in data['listings']:
            if listing['id'] == listing_id and listing.get('status') == 'active':
                return listing
        return None
    
    def get_user_listings(self, user_id):
        data = self.db.read()
        return [l for l in data['listings'] if l['seller_id'] == user_id and l.get('status') == 'active']
    
    def buy_listing(self, listing_id, buyer_id):
        data = self.db.read()
        
        listing = None
        listing_index = -1
        for i, l in enumerate(data['listings']):
            if l['id'] == listing_id and l.get('status') == 'active':
                listing = l
                listing_index = i
                break
        
        if not listing:
            return {'ok': False, 'msg': '❌ Объявление не найдено!'}
        
        if listing['seller_id'] == buyer_id:
            return {'ok': False, 'msg': '❌ Нельзя купить свой NFT!'}
        
        buyer = core.db.get(buyer_id)
        if buyer['balance'] < listing['price']:
            return {'ok': False, 'msg': f'❌ Недостаточно средств! Нужно: {fmt(listing["price"])}'}
        
        core.db.update(buyer_id, balance=buyer['balance'] - listing['price'])
        
        seller = core.db.get(listing['seller_id'])
        core.db.update(listing['seller_id'], balance=seller['balance'] + listing['price'])
        
        inv_data = core.shop.inv.read()
        buyer_inv = inv_data.get(str(buyer_id), [])
        
        nft_copy = listing['nft'].copy()
        nft_copy['purchased_at'] = datetime.datetime.now().isoformat()
        nft_copy['unique_id'] = f"{buyer_id}_{nft_copy['item_id']}_{nft_copy.get('global_number', 0)}_{random.randint(1000,9999)}"
        nft_copy['is_upgraded'] = False
        
        buyer_inv.append(nft_copy)
        inv_data[str(buyer_id)] = buyer_inv
        core.shop.inv.write(inv_data)
        
        data['listings'][listing_index]['status'] = 'sold'
        data['listings'][listing_index]['buyer_id'] = buyer_id
        data['listings'][listing_index]['sold_at'] = datetime.datetime.now().isoformat()
        self.db.write(data)
        
        return {'ok': True, 'msg': f'✅ NFT куплен за {fmt(listing["price"])}', 'nft': nft_copy}
    
    def cancel_listing(self, listing_id, seller_id):
        data = self.db.read()
        
        for i, listing in enumerate(data['listings']):
            if listing['id'] == listing_id and listing.get('status') == 'active':
                if listing['seller_id'] != seller_id:
                    return {'ok': False, 'msg': '❌ Это не ваше объявление!'}
                
                inv_data = core.shop.inv.read()
                seller_inv = inv_data.get(str(seller_id), [])
                
                nft_copy = listing['nft'].copy()
                nft_copy['purchased_at'] = datetime.datetime.now().isoformat()
                nft_copy['unique_id'] = f"{seller_id}_{nft_copy['item_id']}_{nft_copy.get('global_number', 0)}_{random.randint(1000,9999)}"
                nft_copy['is_upgraded'] = False
                
                seller_inv.append(nft_copy)
                inv_data[str(seller_id)] = seller_inv
                core.shop.inv.write(inv_data)
                
                data['listings'][i]['status'] = 'cancelled'
                data['listings'][i]['cancelled_at'] = datetime.datetime.now().isoformat()
                self.db.write(data)
                
                return {'ok': True, 'msg': '✅ Объявление отменено, NFT возвращён'}
        
        return {'ok': False, 'msg': '❌ Объявление не найдено!'}

# === ИГРЫ ===
class Games:
    def __init__(self, db): 
        self.db = db
    
    def can(self, uid, amount): 
        return self.db.get(uid)['balance'] >= amount
    
    def coin(self, uid, bet, choice):
        if not self.can(uid, bet): 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        result = random.choice(['орел', 'решка'])
        win = choice == result
        if win:
            win_amount = bet * 2
            self.db.update(uid, balance=user['balance'] - bet + win_amount, 
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            return {'ok': True, 'win': True, 'res': result, 'amount': win_amount, 'balance': user['balance'] - bet + win_amount}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'res': result, 'amount': bet, 'balance': user['balance'] - bet}
    
    def slots(self, uid, bet):
        if not self.can(uid, bet): 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        symbols = ['🍒','🍋','🍊','🍇','🔔','💎','7️⃣']
        reels = [random.choice(symbols) for _ in range(3)]
        if reels[0] == reels[1] == reels[2]:
            mult = 10 if reels[0] == '7️⃣' else 5
            win = bet * mult
            self.db.update(uid, balance=user['balance'] - bet + win,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            return {'ok': True, 'win': True, 'reels': reels, 'mult': mult, 'amount': win, 'balance': user['balance'] - bet + win}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'reels': reels, 'amount': bet, 'balance': user['balance'] - bet}
    
    def dice(self, uid, bet, pred):
        if not self.can(uid, bet): 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        if pred < 1 or pred > 6: 
            return {'ok': False, 'msg': '❌ Число от 1 до 6!'}
        user = self.db.get(uid)
        self.db.update(uid, balance=user['balance'] - bet)
        roll = random.randint(1,6)
        win = pred == roll
        if win:
            win_amount = bet * 6
            self.db.update(uid, balance=user['balance'] - bet + win_amount,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            return {'ok': True, 'win': True, 'roll': roll, 'amount': win_amount, 'balance': user['balance'] - bet + win_amount}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'roll': roll, 'amount': bet, 'balance': user['balance'] - bet}

# === ИГРА КРАШ ===
class CrashGame:
    def __init__(self, db): 
        self.db = db
        self.games = {}
    
    def start(self, uid, bet, target):
        if uid in self.games: 
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её командой /cancel_game'}
        user = self.db.get(uid)
        if user['balance'] < bet: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        if target < 1.1 or target > 100: 
            return {'ok': False, 'msg': '❌ Множитель от 1.1 до 100'}
        new_balance = user['balance'] - bet
        self.db.update(uid, balance=new_balance)
        crash = round(1.0 / (1.0 - random.random() * 0.95), 2)
        if crash >= target:
            win = int(bet * target)
            self.db.update(uid, balance=new_balance + win, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            return {'ok': True, 'win': True, 'crash': crash, 'amount': win, 'balance': new_balance + win}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'crash': crash, 'amount': bet, 'balance': new_balance}
    
    def cancel_game(self, uid):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Игра отменена. Ставка {fmt(g["bet"])} возвращена.'}

# === ИГРА МИНЫ ===
class Mines:
    def __init__(self, db): 
        self.db = db
        self.games = {}
    
    def mults(self, count):
        mults = {}
        for cells in range(1, 25):
            if count == 1:
                mult = 1 + cells * 0.06
                max_mult = 5
            elif count == 2:
                mult = 1 + cells * 0.17
                max_mult = 10
            elif count == 3:
                mult = 1 + cells * 0.38
                max_mult = 15
            elif count == 4:
                mult = 1 + cells * 0.49
                max_mult = 20
            elif count == 5:
                mult = 1 + cells * 0.60
                max_mult = 25
            elif count == 6:
                mult = 1 + cells * 0.81
                max_mult = 30
            else:
                mult = 1 + cells * (count * 0.15)
                max_mult = 30
            mults[cells] = round(min(mult, max_mult), 2)
        return mults
    
    def start(self, uid, bet, mines=3):
        if uid in self.games: 
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её командой /cancel_game'}
        
        if mines < 1 or mines > 6:
            return {'ok': False, 'msg': '❌ Количество мин должно быть от 1 до 6!'}
        
        user = self.db.get(uid)
        if user['balance'] < bet: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        new_balance = user['balance'] - bet
        self.db.update(uid, balance=new_balance)
        
        field = [['⬜']*5 for _ in range(5)]
        
        mpos = []
        while len(mpos) < mines:
            p = (random.randint(0,4), random.randint(0,4))
            if p not in mpos: 
                mpos.append(p)
        
        self.games[uid] = {
            'bet': bet, 
            'field': field, 
            'mines': mpos, 
            'count': mines, 
            'opened': [], 
            'mult': 1.0, 
            'mults': self.mults(mines), 
            'won': 0, 
            'bal': new_balance
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, r, c):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[uid]
        if (r,c) in g['opened']: 
            return {'ok': False, 'msg': '❌ Уже открыто!'}
        
        if (r,c) in g['mines']:
            for rr,cc in g['mines']: 
                g['field'][rr][cc] = '💣'
            g['field'][r][c] = '💥'
            
            opened = len(g['opened'])
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'over': True, 'field': g['field'], 'opened': opened, 'bet': g['bet']}
        
        g['opened'].append((r,c))
        g['field'][r][c] = '🟩'
        opened = len(g['opened'])
        g['mult'] = g['mults'].get(opened, 2.5)
        g['won'] = int(g['bet'] * g['mult'])
        
        if opened >= 25 - g['count']:
            user = self.db.get(uid)
            new_bal = g['bal'] + g['won']
            self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            
            for rr,cc in g['mines']: 
                g['field'][rr][cc] = '💣'
            
            del self.games[uid]
            return {'ok': True, 'over': True, 'win': True, 'field': g['field'], 
                   'opened': opened, 'won': g['won'], 'balance': new_bal, 'mult': g['mult']}
        
        return {'ok': True, 'over': False, 'field': g['field'], 'opened': opened, 
                'mult': g['mult'], 'won': g['won'], 'max': 25 - g['count']}
    
    def cashout(self, uid):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[uid]
        if not g['opened']: 
            return {'ok': False, 'msg': '❌ Сначала откройте клетку!'}
        
        user = self.db.get(uid)
        new_bal = g['bal'] + g['won']
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        
        for rr,cc in g['mines']: 
            g['field'][rr][cc] = '💣'
        
        field = [row[:] for row in g['field']]
        del self.games[uid]
        return {'ok': True, 'won': g['won'], 'balance': new_bal, 'field': field, 
                'opened': len(g['opened']), 'mult': g['mult']}
    
    def cancel_game(self, uid):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Игра отменена. Ставка {fmt(g["bet"])} возвращена.'}
    
    def kb(self, uid, field, active=True):
        kb = []
        for i in range(5):
            row = []
            for j in range(5):
                if field[i][j] in ['🟩','💣','💥']:
                    row.append(InlineKeyboardButton(text=field[i][j], callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(text="🟦" if active else "⬛", callback_data=f"mines_{uid}_{i}_{j}"))
            kb.append(row)
        if active: 
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"cashout_{uid}")])
        kb.append([InlineKeyboardButton(text="🎮 Новая", callback_data="mines_new")])
        return InlineKeyboardMarkup(inline_keyboard=kb)

# === ИГРА БАШНЯ ===
class Tower:
    def __init__(self, db): 
        self.db = db
        self.games = {}
        self.base = [1.2, 1.5, 2.0, 2.5, 3.2, 4.0, 5.0, 6.0, 7.0]
    
    def mults(self, mines):
        if mines == 1:
            return self.base
        elif mines == 2:
            return [round(x * 1.4, 2) for x in self.base]
        elif mines == 3:
            return [round(x * 1.8, 2) for x in self.base]
        elif mines == 4:
            return [round(x * 2.2, 2) for x in self.base]
        return self.base
    
    def start(self, uid, bet, mines=1):
        if uid in self.games: 
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её командой /cancel_game'}
        
        if mines < 1 or mines > 4: 
            return {'ok': False, 'msg': '❌ Мины от 1 до 4!'}
        
        user = self.db.get(uid)
        if user['balance'] < bet: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        
        row = {
            'cells': ['⬜']*5, 
            'mines': random.sample(range(5), mines), 
            'revealed': False
        }
        
        self.games[uid] = {
            'bet': bet, 
            'mines': mines, 
            'row': 0, 
            'rows': [row], 
            'opened': [], 
            'mult': 1.0, 
            'mults': self.mults(mines), 
            'bal': new_bal, 
            'won': 0
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, r, c):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[uid]
        
        if r != g['row']: 
            return {'ok': False, 'msg': '❌ Можно открывать только текущий ряд!'}
        
        if f"{r}_{c}" in g['opened']: 
            return {'ok': False, 'msg': '❌ Эта клетка уже открыта!'}
        
        row = g['rows'][r]
        
        if c in row['mines']:
            for i in range(5): 
                row['cells'][i] = '💣' if i in row['mines'] else '⬛'
            row['cells'][c] = '💥'
            
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'over': True, 'mine': True, 'row_data': row, 'bet': g['bet']}
        
        g['opened'].append(f"{r}_{c}")
        row['cells'][c] = '🟩'
        g['mult'] = g['mults'][r]
        g['won'] = int(g['bet'] * g['mult'])
        
        if r >= 8:
            user = self.db.get(uid)
            new_bal = g['bal'] + g['won']
            self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            del self.games[uid]
            return {'ok': True, 'over': True, 'win': True, 'won': g['won'], 'mult': g['mult'], 'rows': r+1, 'balance': new_bal}
        
        g['row'] += 1
        
        if len(g['rows']) <= g['row']:
            g['rows'].append({
                'cells': ['⬜']*5, 
                'mines': random.sample(range(5), g['mines']), 
                'revealed': False
            })
        
        return {'ok': True, 'over': False, 'row': r, 'col': c, 'next': g['row'], 
                'mult': g['mult'], 'won': g['won']}
    
    def cashout(self, uid):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[uid]
        if not g['opened']: 
            return {'ok': False, 'msg': '❌ Сначала откройте клетку!'}
        
        user = self.db.get(uid)
        new_bal = g['bal'] + g['won']
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        del self.games[uid]
        return {'ok': True, 'won': g['won'], 'mult': g['mult'], 'rows': g['row'], 'balance': new_bal}
    
    def cancel_game(self, uid):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        
        g = self.games[uid]
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Игра отменена. Ставка {fmt(g["bet"])} возвращена.'}
    
    def kb(self, uid, g):
        kb = []
        for r in range(len(g['rows'])):
            row = g['rows'][r]
            btns = []
            if r < g['row']:
                for c in range(5):
                    if f"{r}_{c}" in g['opened']: 
                        btns.append(InlineKeyboardButton(text="🟩", callback_data="ignore"))
                    else: 
                        btns.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            elif r == g['row']:
                for c in range(5): 
                    btns.append(InlineKeyboardButton(text="🟦", callback_data=f"tower_{uid}_{r}_{c}"))
            else:
                for c in range(5): 
                    btns.append(InlineKeyboardButton(text="⬛", callback_data="ignore"))
            kb.append(btns)
        
        if g['opened']: 
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"tower_cash_{uid}")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)

# === ИГРА РУЛЕТКА ===
class Roulette:
    def __init__(self, db): 
        self.db = db
        self.red = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    
    def play(self, uid, bet, btype, val=None):
        user = self.db.get(uid)
        if user['balance'] < bet: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        self.db.update(uid, balance=user['balance'] - bet)
        num = random.randint(0,36)
        color = 'green' if num == 0 else ('red' if num in self.red else 'black')
        win = False
        mult = 0
        if btype == 'even' and num != 0 and num % 2 == 0: 
            win, mult = True, 2
        elif btype == 'odd' and num != 0 and num % 2 == 1: 
            win, mult = True, 2
        elif btype == 'red' and color == 'red': 
            win, mult = True, 2
        elif btype == 'black' and color == 'black': 
            win, mult = True, 2
        elif btype == '1-12' and 1 <= num <= 12: 
            win, mult = True, 3
        elif btype == '13-24' and 13 <= num <= 24: 
            win, mult = True, 3
        elif btype == '25-36' and 25 <= num <= 36: 
            win, mult = True, 3
        elif btype == 'zero' and num == 0: 
            win, mult = True, 36
        elif btype == 'number' and val is not None and num == val: 
            win, mult = True, 36
        if win:
            win_amount = bet * mult
            self.db.update(uid, balance=user['balance'] - bet + win_amount,
                          games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            return {'ok': True, 'win': True, 'num': num, 'color': color, 'amount': win_amount, 'mult': mult, 'balance': user['balance'] - bet + win_amount}
        else:
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            return {'ok': True, 'win': False, 'num': num, 'color': color, 'amount': bet, 'balance': user['balance'] - bet}

# === ИГРА ЗОЛОТО ===
class Gold:
    def __init__(self, db): 
        self.db = db
        self.games = {}
        self.mults = [2,4,8,16,32,64,128,256,512,1024,2048,4096]
    
    def start(self, uid, bet, chat_id=None):
        if uid in self.games: 
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её командой /cancel_game'}
        user = self.db.get(uid)
        if user['balance'] < bet: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        self.games[uid] = {
            'bet': bet, 
            'level': 0, 
            'won': 0, 
            'bal': new_bal, 
            'history': [],
            'chat_id': chat_id, 
            'uid': uid
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def choose(self, uid, choice, chat_id=None):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Это не ваш чат!'}
        
        money = random.randint(1,2)
        win = choice == money
        g['history'].append({'level': g['level']+1, 'choice': choice, 'money': money, 'win': win})
        
        if win:
            g['level'] += 1
            g['won'] = g['bet'] * self.mults[g['level']-1]
            if g['level'] >= 12:
                user = self.db.get(uid)
                new_bal = g['bal'] + g['won']
                self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
                del self.games[uid]
                return {'ok': True, 'win': True, 'max': True, 'won': g['won'], 'mult': self.mults[g['level']-1], 'level': g['level'], 'balance': new_bal}
            return {'ok': True, 'win': True, 'level': g['level'], 'mult': self.mults[g['level']-1], 'won': g['won'], 'money': money, 'choice': choice, 'game_over': False}
        else:
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'win': False, 'level': g['level'], 'bet': g['bet'], 'money': money, 'choice': choice, 'game_over': True, 'mult': self.mults[g['level']] if g['level'] < 12 else self.mults[g['level']-1]}
    
    def cashout(self, uid, chat_id=None):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Это не ваш чат!'}
        
        if g['level'] == 0: 
            return {'ok': False, 'msg': '❌ Сначала выберите сторону!'}
        
        user = self.db.get(uid)
        new_bal = g['bal'] + g['won']
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        del self.games[uid]
        return {'ok': True, 'won': g['won'], 'level': g['level'], 'mult': self.mults[g['level']-1], 'balance': new_bal}
    
    def cancel_game(self, uid, chat_id=None):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Это не ваш чат!'}
        
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Игра отменена. Ставка {fmt(g["bet"])} возвращена.'}
    
    def kb(self, uid, g):
        kb = [[
            InlineKeyboardButton(text="⬅️ Левая", callback_data=f"gold_left_{uid}"),
            InlineKeyboardButton(text="➡️ Правая", callback_data=f"gold_right_{uid}")
        ]]
        if g['level'] > 0: 
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"gold_cash_{uid}")])
        return InlineKeyboardMarkup(inline_keyboard=kb)
    
    def display(self, g, res=None):
        loss = res and not res.get('win', False) and res.get('game_over', False)
        text = "💥 **Ты проиграл!**\nПопробуй еще раз!\n• • • • • • • • • • • • •\n" if loss else "🎰 **ЗОЛОТО**\n\n"
        for i in range(12,0,-1):
            mult = self.mults[i-1]
            win = g['bet'] * mult
            if i <= g['level']:
                hist = next((h for h in g.get('history',[]) if h['level'] == i), None)
                if hist and hist['win']:
                    text += f"|💸|🧨|  {fmt(win)} mDrops ({mult}x)\n" if hist['choice'] == 1 else f"|🧨|💸|  {fmt(win)} mDrops ({mult}x)\n"
                else:
                    text += f"|💸|🧨|  {fmt(win)} mDrops ({mult}x)\n" if i % 2 == 0 else f"|🧨|💸|  {fmt(win)} mDrops ({mult}x)\n"
            elif i == g['level'] + 1 and loss:
                text += f"|💥|💸|  {fmt(win)} mDrops ({mult}x)\n" if res and res.get('choice') == 1 else f"|💸|💥|  {fmt(win)} mDrops ({mult}x)\n"
            else:
                text += f"|❓|❓|  ??? mDrops ({mult}x)\n"
        return text

# === ИГРА РИСК ===
class Risk:
    def __init__(self, db): 
        self.db = db
        self.games = {}
        self.mults = [1.2,1.5,2.0,2.5,3.0,4.0,5.0]
    
    def start(self, uid, bet, chat_id=None):
        if uid in self.games: 
            return {'ok': False, 'msg': '❌ Уже есть активная игра! Завершите её командой /cancel_game'}
        user = self.db.get(uid)
        if user['balance'] < bet: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        new_bal = user['balance'] - bet
        self.db.update(uid, balance=new_bal)
        cells = []
        win_idx = random.sample(range(6), 3)
        for i in range(6):
            if i in win_idx:
                cells.append({'type': 'win', 'mult': random.choice(self.mults), 'revealed': False})
            else:
                cells.append({'type': 'bomb', 'revealed': False})
        random.shuffle(cells)
        self.games[uid] = {
            'bet': bet, 
            'level': 0, 
            'cells': cells, 
            'won': 0, 
            'total_mult': 0.0,
            'bal': new_bal, 
            'opened': [],
            'win_cells_opened': 0,
            'chat_id': chat_id, 
            'uid': uid
        }
        return {'ok': True, 'data': self.games[uid]}
    
    def open(self, uid, idx, chat_id=None):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Это не ваш чат!'}
        
        if idx in g['opened']: 
            return {'ok': False, 'msg': '❌ Уже открыто!'}
        
        cell = g['cells'][idx]
        cell['revealed'] = True
        g['opened'].append(idx)
        
        if cell['type'] == 'bomb':
            user = self.db.get(uid)
            self.db.update(uid, games_played=user.get('games_played',0)+1)
            del self.games[uid]
            return {'ok': True, 'win': False, 'cell': cell, 'game_over': True}
        
        g['level'] += 1
        g['win_cells_opened'] += 1
        g['total_mult'] += cell['mult']
        g['won'] = int(g['bet'] * g['total_mult'])
        
        if g['win_cells_opened'] >= 3:
            user = self.db.get(uid)
            new_bal = g['bal'] + g['won']
            self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
            del self.games[uid]
            return {'ok': True, 'win': True, 'max': True, 'won': g['won'], 'total_mult': g['total_mult'], 'balance': new_bal}
        
        return {'ok': True, 'win': True, 'cell': cell, 'level': g['level'], 'total_mult': g['total_mult'], 'won': g['won']}
    
    def cashout(self, uid, chat_id=None):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Это не ваш чат!'}
        
        if g['level'] == 0: 
            return {'ok': False, 'msg': '❌ Сначала откройте клетку!'}
        
        user = self.db.get(uid)
        new_bal = g['bal'] + g['won']
        self.db.update(uid, balance=new_bal, games_played=user.get('games_played',0)+1, wins=user.get('wins',0)+1)
        del self.games[uid]
        return {'ok': True, 'won': g['won'], 'level': g['level'], 'total_mult': g['total_mult'], 'balance': new_bal}
    
    def cancel_game(self, uid, chat_id=None):
        if uid not in self.games: 
            return {'ok': False, 'msg': '❌ Нет активной игры!'}
        g = self.games[uid]
        
        if g.get('chat_id') and chat_id and g['chat_id'] != chat_id:
            return {'ok': False, 'msg': '❌ Это не ваш чат!'}
        
        user = self.db.get(uid)
        new_bal = user['balance'] + g['bet']
        self.db.update(uid, balance=new_bal)
        del self.games[uid]
        return {'ok': True, 'msg': f'✅ Игра отменена. Ставка {fmt(g["bet"])} возвращена.'}
    
    def kb(self, uid, g):
        kb = []
        row1, row2 = [], []
        for i, cell in enumerate(g['cells']):
            text = "❓"
            if cell['revealed']:
                text = f"✅ {cell['mult']}x" if cell['type'] == 'win' else "💥"
            btn = InlineKeyboardButton(text=text, callback_data=f"risk_cell_{uid}_{i}")
            if i < 3: 
                row1.append(btn)
            else: 
                row2.append(btn)
        kb.append(row1)
        kb.append(row2)
        if g['level'] > 0 and g['win_cells_opened'] < 3:
            kb.append([InlineKeyboardButton(text="🏆 Забрать", callback_data=f"risk_cash_{uid}")])
        return InlineKeyboardMarkup(inline_keyboard=kb)
    
    def display(self, g):
        return f"🎲 **РИСК**\n\n💰 Ставка: {fmt(g['bet'])}\n📊 Уровень: {g['level']}/3\n📈 Сумма множителей: x{g['total_mult']:.2f}\n💎 Текущий выигрыш: {fmt(g['won'])}"

# === БАНК ===
class Bank:
    def __init__(self):
        self.db = DB(BANK_DATA_FILE)
        self.settings = DB(BANK_SETTINGS_FILE)
        if not self.settings.read():
            self.settings.write({'deposit_rates': {'7':3.0,'14':4.5,'30':6.0,'90':8.0,'180':10.0,'365':12.0},
                                 'loan_rates': {'7':5.0,'14':7.0,'30':10.0,'90':12.0,'180':15.0,'365':20.0}, 
                                 'max_loan_amount': 1000000, 'min_credit_score': 300})
    
    def get(self, uid):
        data = self.db.read()
        uid = str(uid)
        if uid not in data:
            data[uid] = {'card_balance': 0, 'deposits': [], 'loans': [], 'credit_history': 500}
            self.db.write(data)
        return data[uid]
    
    def update(self, uid, **kwargs):
        data = self.db.read()
        uid = str(uid)
        if uid not in data: 
            data[uid] = self.get(uid)
        data[uid].update(kwargs)
        self.db.write(data)
    
    def card_deposit(self, uid, amount, main_bal):
        if amount <= 0: 
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        if main_bal < amount: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        b = self.get(uid)
        self.update(uid, card_balance=b['card_balance'] + amount)
        return {'ok': True, 'msg': f'✅ На карту зачислено: {fmt(amount)}'}
    
    def card_withdraw(self, uid, amount, main_bal):
        if amount <= 0: 
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        b = self.get(uid)
        if b['card_balance'] < amount: 
            return {'ok': False, 'msg': '❌ Недостаточно на карте!'}
        self.update(uid, card_balance=b['card_balance'] - amount)
        return {'ok': True, 'msg': f'✅ С карты снято: {fmt(amount)}'}
    
    def create_deposit(self, uid, amount, days, main_bal):
        if amount <= 0: 
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        if main_bal < amount: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        rates = self.settings.read()['deposit_rates']
        if str(days) not in rates: 
            return {'ok': False, 'msg': '❌ Неверный срок!'}
        b = self.get(uid)
        dep = {'id': f"dep_{uid}_{len(b['deposits'])}_{random.randint(100,999)}", 'amount': amount, 'days': days,
               'rate': rates[str(days)], 'start_date': datetime.datetime.now().isoformat(),
               'end_date': (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(), 'status': 'active'}
        b['deposits'].append(dep)
        self.update(uid, deposits=b['deposits'])
        return {'ok': True, 'msg': f'🏦 Вклад создан! Доход: {fmt(int(amount * rates[str(days)] / 100))}'}
    
    def close_deposit(self, uid, dep_id):
        b = self.get(uid)
        for i, d in enumerate(b['deposits']):
            if d['id'] == dep_id and d['status'] == 'active':
                b['deposits'][i]['status'] = 'closed_early'
                self.update(uid, deposits=b['deposits'])
                return {'ok': True, 'amount': d['amount']}
        return {'ok': False, 'msg': '❌ Вклад не найден!'}
    
    def create_loan(self, uid, amount, days, main_bal):
        if amount <= 0: 
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        s = self.settings.read()
        if str(days) not in s['loan_rates']: 
            return {'ok': False, 'msg': '❌ Доступно: 7, 14, 30, 90, 180, 365 дней'}
        if amount > s['max_loan_amount']: 
            return {'ok': False, 'msg': f'❌ Макс сумма: {fmt(s["max_loan_amount"])}'}
        b = self.get(uid)
        if b['credit_history'] < s['min_credit_score']: 
            return {'ok': False, 'msg': f'❌ Низкий рейтинг: {b["credit_history"]}'}
        total = int(amount * (1 + s['loan_rates'][str(days)] / 100))
        loan = {'id': f"loan_{uid}_{len(b['loans'])}_{random.randint(100,999)}", 'amount': amount, 'days': days,
                'rate': s['loan_rates'][str(days)], 'total_to_return': total, 'remaining': total,
                'daily_payment': total // days, 'start_date': datetime.datetime.now().isoformat(),
                'end_date': (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(), 'status': 'active'}
        b['loans'].append(loan)
        self.update(uid, loans=b['loans'])
        return {'ok': True, 'msg': f'🏦 Кредит одобрен! К возврату: {fmt(total)}'}
    
    def pay_loan(self, uid, loan_id, amount, main_bal):
        if amount <= 0: 
            return {'ok': False, 'msg': '❌ Неверная сумма!'}
        if main_bal < amount: 
            return {'ok': False, 'msg': '❌ Недостаточно средств!'}
        b = self.get(uid)
        for i, l in enumerate(b['loans']):
            if l['id'] == loan_id and l['status'] == 'active':
                if amount > l['remaining']: 
                    amount = l['remaining']
                l['remaining'] -= amount
                if l['remaining'] <= 0:
                    l['status'] = 'paid'
                    b['credit_history'] = min(1000, b['credit_history'] + 50)
                self.update(uid, loans=b['loans'], credit_history=b['credit_history'])
                return {'ok': True, 'msg': f'✅ Оплачено: {fmt(amount)}'}
        return {'ok': False, 'msg': '❌ Кредит не найден!'}
    
    def menu(self, uid):
        b = self.get(uid)
        active_deps = [d for d in b['deposits'] if d['status'] == 'active']
        active_loans = [l for l in b['loans'] if l['status'] == 'active']
        return f"🏦 **БАНК**\n\n💳 Карта: {fmt(b['card_balance'])}\n📊 Рейтинг: {b['credit_history']}/1000\n\n💰 Вклады: {len(active_deps)} на {fmt(sum(d['amount'] for d in active_deps))}\n💸 Кредиты: {len(active_loans)} на {fmt(sum(l['remaining'] for l in active_loans))}"

# === ОСНОВНОЙ БОТ ===
class BotCore:
    def __init__(self):
        self.db = UserDB()
        self.promo = PromoDB()
        self.shop = ShopDB()
        self.status = StatusShop()
        self.bank = Bank()
        self.market = Market()
        self.ban = BanDB()
        self.admins = AdminDB()
        self.logs = AdminLogs()
        self.games = Games(self.db)
        self.crash = CrashGame(self.db)
        self.mines = Mines(self.db)
        self.tower = Tower(self.db)
        self.roulette = Roulette(self.db)
        self.gold = Gold(self.db)
        self.risk = Risk(self.db)
    
    def parse_bet(self, text, bal=None):
        if not text: 
            return 0
        text = text.lower().strip()
        if text == 'все' and bal is not None: 
            return bal
        m = re.match(r'^(\d+(?:\.\d+)?)(к+)$', text)
        if m:
            n, k = float(m[1]), len(m[2])
            return int(n * [1000, 1000000, 1000000000][min(k-1, 2)])
        try: 
            return int(text)
        except: 
            return 0

# === ГЛОБАЛЬНЫЕ ФУНКЦИИ ===
core = BotCore()

def is_creator(uid):
    """Проверка на создателя"""
    return core.admins.is_creator(uid)

def is_admin(uid):
    """Проверка на любого админа (включая создателя)"""
    return core.admins.is_admin(uid)

def is_private(msg): 
    return msg.chat.type == 'private'

def fmt(n):
    if n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.1f}кккк"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}ккк"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}кк"
    if n >= 1000:
        return f"{n/1000:.1f}к"
    return str(n)

# === MIDDLEWARE ДЛЯ ПРОВЕРКИ БАНА ===
async def ban_middleware(handler, event: Message, data: dict):
    if isinstance(event, Message):
        user_id = event.from_user.id
        if core.ban.is_banned(user_id) and not is_creator(user_id):
            ban_info = core.ban.get_ban_info(user_id)
            await event.reply(f"⛔ **Вы забанены!**\n\nПричина: {ban_info['reason']}\nДата: {ban_info['banned_at'][:10]}")
            return
    return await handler(event, data)

# === КОМАНДА ИГРЫ ===
async def cmd_games(msg):
    games_text = """
🎮 **СПИСОК ИГР И ПРИМЕРЫ**

🎲 **Монетка**
• Пример: `монетка 1000 орел`
• Ставка: 1000, выбор: орел/решка
• Выигрыш: x2

🎰 **Слоты**
• Пример: `слоты 5000`
• Ставка: 5000
• Выигрыш: x5 или x10

🎯 **Кубик**
• Пример: `кубик 2000 5`
• Ставка: 2000, число: 1-6
• Выигрыш: x6

🚀 **Краш**
• Пример: `краш 10000 2.5`
• Ставка: 10000, множитель: от 1.1 до 100
• Выигрыш: ставка × множитель

💣 **Мины**
• Пример: `мины 5000 5`
• Ставка: 5000, мин: от 1 до 6
• Множитель растёт с каждым ходом

🏗️ **Башня**
• Пример: `башня 3000 2`
• Ставка: 3000, мин на этаж: 1-4
• **Максимальные множители:**
  • 1 мина: x7.0
  • 2 мины: x9.8
  • 3 мины: x12.6
  • 4 мины: x15.4

🎰 **Рулетка**
• Пример: `рулетка 1000 чет`
• Ставка: 1000, типы: чет/нечет, красное/черное, 1-12, 13-24, 25-36, зеро, число
• Множители: x2, x3, x36

💰 **Золото**
• Пример: `золото 2000`
• Ставка: 2000
• 50/50, множители до 4096x

🎲 **Риск**
• Пример: `риск 1500`
• Ставка: 1500
• 6 клеток, 3 выигрышных, 3 проигрышных

💰 **ОСОБАЯ СТАВКА:**
• `все` - поставить ВЕСЬ баланс
• Пример: `мины все 5`

❌ **Отмена игры:**
• `/cancel_game` - отменить текущую игру и вернуть ставку
"""
    await msg.reply(games_text, parse_mode="Markdown")

# === КОМАНДА ОТМЕНЫ ИГРЫ ===
async def cmd_cancel_game(msg: Message):
    uid = msg.from_user.id
    chat_id = msg.chat.id
    cancelled = False
    msg_text = ""
    
    if uid in core.crash.games:
        res = core.crash.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.mines.games:
        res = core.mines.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.tower.games:
        res = core.tower.cancel_game(uid)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.gold.games:
        res = core.gold.cancel_game(uid, chat_id)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if uid in core.risk.games:
        res = core.risk.cancel_game(uid, chat_id)
        if res['ok']:
            msg_text += res['msg'] + "\n"
            cancelled = True
    
    if cancelled:
        await msg.reply(msg_text.strip())
    else:
        await msg.reply("❌ У вас нет активных игр!")

# === КОМАНДА СТАТУС ===
async def cmd_status(msg):
    user = core.db.get(msg.from_user.id)
    statuses = core.status.all()
    status = statuses.get(user['status'], statuses['novice'])
    
    last_bonus = user.get('last_bonus')
    bonus_info = "Никогда"
    if last_bonus:
        try:
            last_time = datetime.datetime.fromisoformat(last_bonus)
            hours_passed = (datetime.datetime.now() - last_time).total_seconds() / 3600
            if hours_passed < 1:
                next_bonus = int((1 - hours_passed) * 60)
                bonus_info = f"Через {next_bonus} мин"
            else:
                bonus_info = "Можно получить сейчас!"
        except:
            bonus_info = "Можно получить сейчас!"
    
    text = f"{status['emoji']} **{status['name']}**\n\n"
    text += f"💰 Бонус: {fmt(status['min_bonus'])} - {fmt(status['max_bonus'])} (каждый час)\n"
    text += f"⏰ Последний бонус: {bonus_info}\n"
    text += f"📝 {status['description']}"
    
    await msg.reply(text, parse_mode="Markdown")

# === КОМАНДА БОНУС ===
async def cmd_bonus(msg):
    res = core.status.get_bonus(msg.from_user.id, core.db)
    await msg.reply(res['msg'], parse_mode="Markdown")

# === КОМАНДА СТАТУСЫ ===
async def cmd_status_shop(msg):
    if not is_private(msg):
        await msg.reply("❌ Магазин статусов доступен только в ЛС!\nПерейдите в ЛС: @DropPepebot")
        return
    
    user = core.db.get(msg.from_user.id)
    statuses = core.status.all()
    
    text = f"🏪 **МАГАЗИН СТАТУСОВ**\n\n"
    text += f"Ваш текущий статус: {statuses[user['status']]['emoji']} {statuses[user['status']]['name']}\n"
    text += f"💰 Баланс: {fmt(user['balance'])}\n\n"
    text += "Доступные статусы:\n\n"
    
    kb = []
    for status_id, status in statuses.items():
        if status_id == user['status']:
            text += f"{status['emoji']} {status['name']} — {fmt(status['price'])}\n"
            text += f"   • Бонус: {fmt(status['min_bonus'])}-{fmt(status['max_bonus'])}\n"
            text += f"   • Уже есть\n\n"
        else:
            kb.append([InlineKeyboardButton(
                text=f"{status['emoji']} {status['name']} — {fmt(status['price'])}",
                callback_data=f"status_view_{status_id}"
            )])
    
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

# === КОМАНДА БАН ===
async def cmd_ban(msg: Message, state: FSMContext):
    """Бан пользователя (доступно всем админам)"""
    if not is_admin(msg.from_user.id):
        return
    
    if not msg.reply_to_message:
        await msg.reply("❌ Эта команда работает только как ответ на сообщение пользователя!\n"
                        "Нажмите на сообщение человека и выберите 'Ответить', затем напишите 'бан [причина]'")
        return
    
    parts = msg.text.split(maxsplit=1)
    reason = parts[1] if len(parts) > 1 else ""
    
    target_id = msg.reply_to_message.from_user.id
    target_username = msg.reply_to_message.from_user.username
    target_name = msg.reply_to_message.from_user.full_name
    
    if is_creator(target_id):
        await msg.reply("❌ Нельзя забанить создателя!")
        return
    
    core.ban.ban(target_id, msg.from_user.id, reason)
    
    core.logs.add_log(
        admin_id=msg.from_user.id,
        action="ban",
        target_id=target_id,
        details=f"Причина: {reason if reason else 'Не указана'}"
    )
    
    username_str = f"@{target_username}" if target_username else f"ID {target_id}"
    reason_str = f" по причине: {reason}" if reason else ""
    
    await msg.reply(f"⛔ {username_str}, данный пользователь был забанен{reason_str}")
    
    try:
        await msg.bot.send_message(
            target_id,
            f"⛔ **Вы были забанены!**\n\nПричина: {reason if reason else 'Не указана'}\nАдминистратор: {msg.from_user.full_name}"
        )
    except:
        pass

# === КОМАНДА РАЗБАН ===
async def cmd_unban(msg: Message):
    """Разбан пользователя (доступно всем админам)"""
    if not is_admin(msg.from_user.id):
        return
    
    target_id = None
    
    if msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
    else:
        parts = msg.text.split()
        if len(parts) > 1:
            try:
                target_id = int(parts[1])
            except:
                await msg.reply("❌ Неверный формат ID!")
                return
    
    if not target_id:
        await msg.reply("❌ Укажите пользователя (ответом на сообщение или ID)")
        return
    
    if core.ban.unban(target_id):
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="unban",
            target_id=target_id
        )
        
        await msg.reply(f"✅ Пользователь с ID {target_id} разбанен")
        
        try:
            await msg.bot.send_message(
                target_id,
                f"✅ Вы были разбанены!"
            )
        except:
            pass
    else:
        await msg.reply(f"❌ Пользователь с ID {target_id} не найден в списке забаненных")

# === КОМАНДА ОБЩИЙ БАЛАНС ===
async def cmd_total_balance(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    
    parts = msg.text.lower().split()
    
    if len(parts) > 2:
        try:
            for part in parts:
                try:
                    target_id = int(part)
                    total = core.db.get_total_balance(target_id)
                    user_data = core.db.get(target_id)
                    bank_data = core.bank.get(target_id)
                    
                    try:
                        user_chat = await msg.bot.get_chat(target_id)
                        name = user_chat.first_name
                    except:
                        name = f"ID {target_id}"
                    
                    text = f"📊 **Общий баланс пользователя {name}**\n\n"
                    text += f"💰 Наличные: {fmt(user_data['balance'])}\n"
                    text += f"💳 На карте: {fmt(bank_data['card_balance'])}\n"
                    text += f"💎 **ИТОГО: {fmt(total)}**"
                    
                    await msg.reply(text)
                    return
                except ValueError:
                    continue
            
            await msg.reply("❌ Неверный ID пользователя!")
            
        except Exception as e:
            await msg.reply("❌ Ошибка при обработке запроса!")
    else:
        all_users = core.db.get_all_users_total_balance()
        
        if not all_users:
            await msg.reply("📊 Нет пользователей")
            return
        
        text = "🏆 **ТОП ПО ОБЩЕМУ БАЛАНСУ (наличные + карта)**\n\n"
        text += "👑 **ТОЛЬКО ДЛЯ АДМИНОВ**\n\n"
        
        for i, (uid, total, cash, card) in enumerate(all_users[:20], 1):
            try:
                user_chat = await msg.bot.get_chat(int(uid))
                name = user_chat.first_name
                if user_chat.last_name:
                    name += f" {user_chat.last_name}"
            except:
                name = f"ID {uid}"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▪️"
            text += f"{medal} {i}. {name}\n"
            text += f"   💰 {fmt(cash)} + 💳 {fmt(card)} = **{fmt(total)}**\n"
        
        await msg.reply(text)

# === КОМАНДА ID ===
async def cmd_id(msg: Message):
    if not msg.reply_to_message:
        await msg.reply("❌ Эта команда работает только как ответ на сообщение пользователя!\n"
                        "Нажмите на сообщение человека и выберите 'Ответить', затем напишите 'ид'")
        return
    
    target_user = msg.reply_to_message.from_user
    username = f"@{target_user.username}" if target_user.username else "нет username"
    
    text = f"<b>📋 Информация о пользователе</b>\n\n"
    text += f"👤 Имя: {target_user.full_name}\n"
    text += f"🆔 ID: <code>{target_user.id}</code>\n"
    text += f"📱 Username: {username}"
    
    await msg.reply(text, parse_mode="HTML")

# === КОМАНДА ПОМОЩЬ ===
async def cmd_help(msg):
    help_text = """
🎮 **ВСЕ КОМАНДЫ БОТА**

**💰 ИГРЫ**
• `игры` - список всех игр с примерами
• `/cancel_game` - отменить текущую игру и вернуть ставку

**🏦 БАНК (только в ЛС)**
• `банк` - главное меню банка
• `карта` - баланс карты
• `положить [сумма]` - на карту
• `снять [сумма]` - с карты
• `вклад [сумма] [дни]` - открыть вклад
• `вклады` - мои вклады
• `кредит [сумма] [дни]` - взять кредит
• `кредиты` - мои кредиты

**📊 ПРОФИЛЬ**
• `баланс` или `б` - проверить баланс
• `профиль` или `п` - профиль с NFT (работает везде)
• `статус` - мой статус
• `статусы` - магазин статусов (только ЛС)
• `бонус` - получить бонус (раз в час)
• `топ` - топ игроков по балансу (без админов)
• `топ статусы` - топ по статусам (без админов)

**🖼️ NFT (только в ЛС)**
• `мои нфт` или `инвентарь` - мои NFT
• `нфт` или `магазин` - магазин NFT
• `рынок` - рынок NFT

**🎫 ПРОМОКОДЫ**
• `промо [код]` - активировать
• `создать промо` - создать (админы бесплатно)
• `мои промо` - список ваших промокодов

**🔄 ПЕРЕВОДЫ**
• `дать [сумма]` - перевести деньги (в ответ)
• `ид` - узнать ID пользователя (в ответ)

💰 **ФОРМАТЫ СТАВОК**
• 1к = 1,000
• 1кк = 1,000,000
• 1ккк = 1,000,000,000
• 1кккк = 1,000,000,000,000
• `все` = весь баланс

✨ Администраторы не участвуют в рейтингах
"""
    await msg.reply(help_text, parse_mode="Markdown")

# === КОМАНДА СТАРТ ===
async def cmd_start(msg): 
    core.db.get(msg.from_user.id)
    await msg.reply(f"🎰 Добро пожаловать, {msg.from_user.first_name}!\n💰 Баланс: {fmt(core.db.get(msg.from_user.id)['balance'])}\n\n📝 help - все команды\n🎮 игры - список игр")

# === КОМАНДА БАЛАНС ===
async def cmd_balance(msg): 
    user = core.db.get(msg.from_user.id)
    await msg.reply(f"💰 Баланс: {fmt(user['balance'])}")

# === КОМАНДА ПРОФИЛЬ ===
async def cmd_profile(msg):
    uid = str(msg.from_user.id)
    user = core.db.get(uid)
    statuses = core.status.all()
    status = statuses.get(user['status'], statuses['novice'])
    
    name = msg.from_user.first_name
    
    games = user.get('games_played', 0)
    wins = user.get('wins', 0)
    win_percent = (wins / games * 100) if games > 0 else 0
    
    inventory = core.shop.inventory(uid)
    sorted_nft = sorted(inventory, key=lambda x: x.get('global_number', 0))
    total_nft = len(inventory)
    
    text = f"📊 **{status['emoji']} {name}**\n"
    text += f"💰 {fmt(user['balance'])}\n"
    text += f"🎮 {games} игр | 🏆 {wins} побед | {win_percent:.1f}%\n\n"
    
    text += f"🎒 NFT ({total_nft}):\n"
    
    if sorted_nft:
        for i, nft in enumerate(sorted_nft[:5], 1):
            emoji = nft.get('emoji', '🎁')
            name_nft = nft.get('name', 'NFT')
            num = nft.get('global_number', '?')
            upgraded = " ✨" if nft.get('is_upgraded') else ""
            text += f"{i}. {emoji} **{name_nft}** #{num}{upgraded}\n"
        
        if total_nft > 5:
            text += f"...и еще {total_nft - 5} NFT"
    else:
        text += "У вас пока нет NFT"
    
    await msg.reply(text, parse_mode="Markdown")

# === КОМАНДА МОИ НФТ ===
async def cmd_my_nft(msg: Message):
    if not is_private(msg):
        await msg.reply("❌ Команда 'мои нфт' доступна только в личных сообщениях с ботом!\nПерейдите в ЛС: @DropPepebot")
        return
    
    uid = str(msg.from_user.id)
    inventory = core.shop.inventory(uid)
    
    if not inventory:
        await msg.reply("📭 У вас нет NFT")
        return
    
    await show_nft_list(msg, uid, 0)

async def show_nft_list(message: Message or CallbackQuery, uid: str, page: int = 0):
    inventory = core.shop.inventory(uid)
    sorted_nft = sorted(inventory, key=lambda x: x.get('global_number', 0))
    items_per_page = 5
    total_pages = (len(sorted_nft) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    current_items = sorted_nft[start:end]
    
    text = f"🖼 **ВАШИ NFT**\n\nСтраница {page + 1}/{total_pages}\n\n"
    
    kb = []
    for nft in current_items:
        emoji = nft.get('emoji', '🎁')
        name = nft.get('name', 'NFT')
        num = nft.get('global_number', '?')
        upgraded = "✨" if nft.get('is_upgraded') else ""
        button_text = f"{emoji} {name} #{num} {upgraded}"
        kb.append([InlineKeyboardButton(text=button_text[:50], callback_data=f"nft_view_{uid}_{nft['unique_id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"nft_page_{uid}_{page-1}"))
    if page + 1 < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"nft_page_{uid}_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_nft_detail(callback: CallbackQuery, uid: str, unique_id: str):
    inventory = core.shop.inventory(uid)
    nft = next((item for item in inventory if item['unique_id'] == unique_id), None)
    
    if not nft:
        await callback.answer("❌ NFT не найден!", show_alert=True)
        return
    
    emoji = nft.get('emoji', '🎁')
    name = nft.get('name', 'NFT')
    num = nft.get('global_number', '?')
    desc = nft.get('description', 'Нет описания')
    upgraded = nft.get('is_upgraded', False)
    upgrade_info = f"\n✨ Улучшен: {nft.get('upgraded_at', 'неизвестно')[:10]}" if upgraded else ""
    purchase_date = nft.get('purchased_at', 'неизвестно')[:10]
    
    text = f"{emoji} **{name}** #{num}\n\n"
    text += f"📝 {desc}\n"
    text += f"📅 Куплен: {purchase_date}{upgrade_info}\n"
    text += f"🆔 `{unique_id[:16]}...`"
    
    kb = [
        [InlineKeyboardButton(text="💰 Продать на рынке", callback_data=f"nft_sell_{uid}_{unique_id}")],
        [InlineKeyboardButton(text="🔄 Передать", callback_data=f"nft_transfer_start_{uid}_{unique_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"nft_back_{uid}")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# === КОМАНДА МАГАЗИН НФТ ===
async def cmd_nft_shop(msg: Message):
    if not is_private(msg):
        await msg.reply("❌ Команда 'нфт' доступна только в личных сообщениях с ботом!\nПерейдите в ЛС: @DropPepebot")
        return
    
    await show_shop_list(msg.from_user.id, msg, 0)

async def show_shop_list(user_id, message: Message or CallbackQuery, page: int = 0):
    items = core.shop.items()
    items_list = list(items.items())
    items_per_page = 5
    total_pages = (len(items_list) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    current_items = items_list[start:end]
    
    text = f"🏪 **МАГАЗИН NFT**\n\nСтраница {page + 1}/{total_pages}\n\n"
    
    kb = []
    for item_id, item in current_items:
        emoji = item.get('emoji', '🎁')
        name = item.get('name', 'NFT')
        price = fmt(item.get('price', 0))
        quantity = item.get('quantity', 0)
        button_text = f"{emoji} {name} - {price} (ост. {quantity})"
        kb.append([InlineKeyboardButton(text=button_text[:50], callback_data=f"shop_view_{item_id}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"shop_page_{page-1}"))
    if page + 1 < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"shop_page_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_shop_item(callback: CallbackQuery, item_id: str):
    items = core.shop.items()
    item = items.get(item_id)
    
    if not item:
        await callback.answer("❌ Товар не найден!", show_alert=True)
        await show_shop_list(callback.from_user.id, callback, 0)
        return
    
    emoji = item.get('emoji', '🎁')
    name = item.get('name', 'NFT')
    price = item.get('price', 0)
    quantity = item.get('quantity', 0)
    sold = item.get('sold', 0)
    desc = item.get('description', 'Нет описания')
    
    user_balance = core.db.get(callback.from_user.id)['balance']
    
    text = f"{emoji} **{name}**\n\n"
    text += f"📝 {desc}\n"
    text += f"💰 Цена: {fmt(price)}\n"
    text += f"📦 Осталось: {quantity} шт | 📊 Продано: {sold}\n\n"
    text += f"💳 Ваш баланс: {fmt(user_balance)}"
    
    kb = []
    if quantity > 0 and user_balance >= price:
        kb.append([InlineKeyboardButton(text="💳 Купить", callback_data=f"shop_buy_{item_id}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="shop_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# === КОМАНДА РЫНОК ===
async def cmd_market(msg: Message):
    if not is_private(msg):
        await msg.reply("❌ Команда 'рынок' доступна только в личных сообщениях с ботом!\nПерейдите в ЛС: @DropPepebot")
        return
    
    await show_market_list(msg.from_user.id, msg, 0)

async def show_market_list(user_id, message: Message or CallbackQuery, page: int = 0):
    listings, total = core.market.get_listings(page, 5)
    
    if not listings:
        text = "🏪 **РЫНОК NFT**\n\n📭 На рынке пока нет NFT"
        kb = [[InlineKeyboardButton(text="🔄 Обновить", callback_data="market_refresh")]]
    else:
        text = f"🏪 **РЫНОК NFT**\n\nСтраница {page + 1}/{(total + 4) // 5}\n\n"
        kb = []
        
        for listing in listings:
            nft = listing['nft']
            try:
                seller_chat = await message.bot.get_chat(listing['seller_id'])
                seller_name = seller_chat.first_name
            except:
                seller_name = f"ID {listing['seller_id']}"
            
            emoji = nft.get('emoji', '🎁')
            name = nft.get('name', 'NFT')
            num = nft.get('global_number', '?')
            button_text = f"{emoji} {name} #{num} - {fmt(listing['price'])} (от {seller_name})"
            if len(button_text) > 50:
                button_text = button_text[:47] + "..."
            kb.append([InlineKeyboardButton(text=button_text, callback_data=f"market_view_{listing['id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"market_page_{page-1}"))
    if (page + 1) * 5 < total:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"market_page_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    kb.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="market_refresh")])
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_market_listing(callback: CallbackQuery, listing_id: int):
    listing = core.market.get_listing(listing_id)
    if not listing:
        await callback.answer("❌ Объявление не найдено!", show_alert=True)
        await show_market_list(callback.from_user.id, callback, 0)
        return
    
    nft = listing['nft']
    
    try:
        seller_chat = await callback.bot.get_chat(listing['seller_id'])
        seller_name = seller_chat.first_name
    except:
        seller_name = f"ID {listing['seller_id']}"
    
    emoji = nft.get('emoji', '🎁')
    name = nft.get('name', 'NFT')
    num = nft.get('global_number', '?')
    desc = nft.get('description', 'Нет описания')
    
    text = f"{emoji} **{name}** #{num}\n\n"
    text += f"📝 {desc}\n"
    text += f"👤 Продавец: {seller_name}\n"
    text += f"💰 Цена: {fmt(listing['price'])}\n"
    text += f"📅 Выставлен: {listing['listed_at'][:10]}\n\n"
    text += f"💳 Ваш баланс: {fmt(core.db.get(callback.from_user.id)['balance'])}"
    
    kb = [
        [InlineKeyboardButton(text="💳 Купить", callback_data=f"market_buy_{listing_id}")],
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="market_back")]
    ]
    
    if listing['seller_id'] == callback.from_user.id:
        kb.insert(0, [InlineKeyboardButton(text="❌ Снять с продажи", callback_data=f"market_cancel_{listing_id}")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# === ПЕРЕДАЧА NFT ===
async def cmd_transfer_nft_start(msg: Message, state: FSMContext):
    if not is_private(msg):
        await msg.reply("❌ Передача NFT доступна только в личных сообщениях с ботом!\nПерейдите в ЛС: @DropPepebot")
        return
    
    args = msg.text.split()
    if len(args) > 1:
        target = args[1].strip()
        
        try:
            user_id = int(target)
            try:
                chat = await msg.bot.get_chat(user_id)
                await state.update_data(
                    target_id=user_id, 
                    target_name=chat.first_name,
                    target_uid=str(user_id)
                )
            except:
                await msg.reply("❌ Пользователь с таким ID не найден! Убедитесь, что пользователь уже писал боту.")
                return
        except ValueError:
            await msg.reply("❌ Неверный формат! Используйте: передать нфт ID (только цифры)")
            return
        
        uid = str(msg.from_user.id)
        inventory = core.shop.inventory(uid)
        
        if not inventory:
            await msg.reply("📭 У вас нет NFT для передачи")
            await state.clear()
            return
        
        await state.set_state(TransferNFTStates.waiting_nft)
        await show_nft_for_transfer(msg, state, uid, 0)
    else:
        await state.set_state(TransferNFTStates.waiting_user)
        await msg.reply("👤 Введите ID пользователя, которому хотите передать NFT (только цифры):")

async def handle_transfer_user_input(msg: Message, state: FSMContext):
    """Обработчик ввода ID пользователя для передачи NFT"""
    target = msg.text.strip()
    
    try:
        user_id = int(target)
        try:
            chat = await msg.bot.get_chat(user_id)
            
            data = await state.get_data()
            unique_id = data.get('transfer_nft_id')
            
            if not unique_id:
                await msg.reply("❌ Ошибка: NFT не найден в состоянии!")
                await state.clear()
                return
            
            uid = str(msg.from_user.id)
            inventory = core.shop.inventory(uid)
            nft = next((item for item in inventory if item['unique_id'] == unique_id), None)
            
            if not nft:
                await msg.reply("❌ NFT не найден в вашем инвентаре!")
                await state.clear()
                return
            
            if uid == str(user_id):
                await msg.reply("❌ Нельзя передать NFT самому себе!")
                await state.clear()
                return
            
            await state.update_data(
                target_id=user_id,
                target_name=chat.first_name,
                target_uid=str(user_id),
                transfer_nft_id=unique_id
            )
            
            emoji = nft.get('emoji', '🎁')
            name = nft.get('name', 'NFT')
            num = nft.get('global_number', '?')
            
            text = f"❓ **ПОДТВЕРДИТЕ ПЕРЕДАЧУ**\n\n"
            text += f"Вы передаете:\n{emoji} **{name}** #{num}\n\n"
            text += f"Пользователю: **{chat.first_name}** (ID: {user_id})\n\n"
            text += "Все верно?"
            
            kb = [
                [InlineKeyboardButton(text="✅ Да, передать", callback_data=f"transfer_confirm_{user_id}_{unique_id}")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="transfer_cancel")]
            ]
            
            await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
            
        except Exception as e:
            await msg.reply(f"❌ Пользователь с таким ID не найден! Убедитесь, что пользователь уже писал боту.\n\nОшибка: {e}")
            return
    except ValueError:
        await msg.reply("❌ Неверный формат! Введите ID пользователя (только цифры)")
        return

async def show_nft_for_transfer(message: Message or CallbackQuery, state: FSMContext, uid: str, page: int = 0):
    inventory = core.shop.inventory(uid)
    sorted_nft = sorted(inventory, key=lambda x: x.get('global_number', 0))
    items_per_page = 5
    total_pages = (len(sorted_nft) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    current_items = sorted_nft[start:end]
    
    text = f"🔄 **ВЫБЕРИТЕ NFT ДЛЯ ПЕРЕДАЧИ**\n\nСтраница {page + 1}/{total_pages}\n\n"
    
    kb = []
    for nft in current_items:
        emoji = nft.get('emoji', '🎁')
        name = nft.get('name', 'NFT')
        num = nft.get('global_number', '?')
        upgraded = "✨" if nft.get('is_upgraded') else ""
        button_text = f"{emoji} {name} #{num} {upgraded}"
        kb.append([InlineKeyboardButton(text=button_text[:50], callback_data=f"transfer_select_{uid}_{nft['unique_id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"transfer_page_{uid}_{page-1}"))
    if page + 1 < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"transfer_page_{uid}_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="transfer_cancel")])
    
    if isinstance(message, Message):
        await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def process_transfer_nft(callback: CallbackQuery, state: FSMContext, uid: str, unique_id: str):
    data = await state.get_data()
    target_id = data.get('target_id')
    target_name = data.get('target_name', f"ID {target_id}")
    
    if not target_id:
        await callback.answer("❌ Данные получателя не найдены!", show_alert=True)
        await state.clear()
        return
    
    if uid == str(target_id):
        await callback.answer("❌ Нельзя передать NFT самому себе!", show_alert=True)
        await state.clear()
        return
    
    inventory = core.shop.inventory(uid)
    nft = next((item for item in inventory if item['unique_id'] == unique_id), None)
    
    if not nft:
        await callback.answer("❌ NFT не найден!", show_alert=True)
        await state.clear()
        return
    
    emoji = nft.get('emoji', '🎁')
    name = nft.get('name', 'NFT')
    num = nft.get('global_number', '?')
    
    text = f"❓ **ПОДТВЕРДИТЕ ПЕРЕДАЧУ**\n\n"
    text += f"Вы передаете:\n{emoji} **{name}** #{num}\n\n"
    text += f"Пользователю: **{target_name}** (ID: {target_id})\n\n"
    text += "Все верно?"
    
    kb = [
        [InlineKeyboardButton(text="✅ Да, передать", callback_data=f"transfer_confirm_{target_id}_{unique_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="transfer_cancel")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def confirm_transfer_nft(callback: CallbackQuery, state: FSMContext, to_uid: str, unique_id: str):
    from_uid = str(callback.from_user.id)
    
    inventory = core.shop.inventory(from_uid)
    nft_exists = any(item['unique_id'] == unique_id for item in inventory)
    
    if not nft_exists:
        await callback.answer("❌ NFT уже не в вашем инвентаре!", show_alert=True)
        await state.clear()
        return
    
    res = core.shop.transfer_nft(from_uid, to_uid, unique_id)
    
    if res['ok']:
        await callback.answer("✅ NFT успешно передан!", show_alert=True)
        await callback.message.edit_text(f"✅ NFT успешно передан пользователю ID: {to_uid}")
        
        try:
            nft = res['nft']
            emoji = nft.get('emoji', '🎁')
            name = nft.get('name', 'NFT')
            num = nft.get('global_number', '?')
            
            await callback.bot.send_message(
                int(to_uid),
                f"🎁 Вам передан NFT!\n\n{emoji} **{name}** #{num}\n\n"
                f"От: {callback.from_user.full_name}"
            )
        except Exception as e:
            print(f"Ошибка при уведомлении получателя: {e}")
    else:
        await callback.answer(res['msg'], show_alert=True)
    
    await state.clear()

async def cmd_cancel_transfer(msg: Message, state: FSMContext):
    """Отмена передачи NFT"""
    current_state = await state.get_state()
    if current_state and current_state.startswith('TransferNFTStates'):
        await state.clear()
        await msg.reply("❌ Передача NFT отменена")
    else:
        await msg.reply("❌ Нет активного процесса передачи NFT")

# === ТОП ===
async def cmd_top(msg):
    top = core.db.top(limit=15)
    
    if not top: 
        await msg.reply("📊 Рейтинг пуст")
        return
    
    text = "🏆 **ТОП ИГРОКОВ**\n\n"
    
    for i, (uid, u) in enumerate(top, 1):
        try: 
            chat = await msg.bot.get_chat(int(uid))
            name = chat.first_name
            if chat.last_name:
                name += f" {chat.last_name}"
        except: 
            name = f"Игрок {uid[-4:]}"
        
        balance = u.get('balance', 0)
        
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = "▪️"
        
        text += f"{medal} {i}. {name} — {fmt(balance)}\n"
    
    text += "\n✨ Администраторы не участвуют в рейтинге"
    
    await msg.reply(text)

async def cmd_top_status(msg):
    top = core.db.top_by_status()
    statuses = core.status.all()
    
    text = "🏆 **ТОП ПО СТАТУСАМ**\n\n"
    
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
    
    has_players = False
    
    for status_id in status_order:
        if status_id in top and top[status_id]:
            status_info = statuses.get(status_id, {'emoji': '🎮', 'name': status_id})
            status_title = status_names.get(status_id, f"{status_info['emoji']} {status_info['name']}")
            text += f"**{status_title}:**\n"
            
            for i, (uid, u) in enumerate(top[status_id][:5], 1):
                user_id = int(uid)
                balance = u.get('balance', 0)
                
                try:
                    chat = await msg.bot.get_chat(user_id)
                    name = chat.first_name
                    if chat.last_name:
                        name += f" {chat.last_name}"
                except:
                    name = f"Игрок {uid[-4:]}"
                
                text += f"   {i}. {name} — {fmt(balance)}\n"
            
            text += "\n"
            has_players = True
    
    if not has_players:
        text += "📊 Пока нет игроков в рейтинге"
    else:
        text += "✨ Администраторы не участвуют в рейтинге"
    
    await msg.reply(text, parse_mode="Markdown")

# === БАНК ===
async def cmd_bank(msg):
    if not is_private(msg): 
        await msg.reply("❌ Банк только в ЛС!\nПерейдите в ЛС: @DropPepebot")
        return
    kb = [[InlineKeyboardButton(text="💳 Карта", callback_data="bank_card"), InlineKeyboardButton(text="📈 Вклады", callback_data="bank_deposits")],
          [InlineKeyboardButton(text="📉 Кредиты", callback_data="bank_loans"), InlineKeyboardButton(text="❓ Помощь", callback_data="bank_help")]]
    await msg.reply(core.bank.menu(msg.from_user.id), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_card(msg):
    if not is_private(msg): 
        await msg.reply("❌ Банк только в ЛС!\nПерейдите в ЛС: @DropPepebot")
        return
    await msg.reply(f"💳 Баланс карты: {fmt(core.bank.get(msg.from_user.id)['card_balance'])}")

async def cmd_deposit(msg, command):
    if not is_private(msg): 
        return
    args = command.args.split() if command.args else []
    if len(args) != 1: 
        await msg.reply("Исп: положить [сумма]")
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0], u['balance'])
    if a <= 0: 
        await msg.reply("❌ Неверная сумма!")
        return
    res = core.bank.card_deposit(msg.from_user.id, a, u['balance'])
    if res['ok']: 
        core.db.update(msg.from_user.id, balance=u['balance'] - a)
    await msg.reply(res['msg'])

async def cmd_withdraw(msg, command):
    if not is_private(msg): 
        return
    args = command.args.split() if command.args else []
    if len(args) != 1: 
        await msg.reply("Исп: снять [сумма]")
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0])
    if a <= 0: 
        await msg.reply("❌ Неверная сумма!")
        return
    res = core.bank.card_withdraw(msg.from_user.id, a, u['balance'])
    if res['ok']: 
        core.db.update(msg.from_user.id, balance=u['balance'] + a)
    await msg.reply(res['msg'])

async def cmd_create_deposit(msg, command):
    if not is_private(msg): 
        return
    args = command.args.split() if command.args else []
    if len(args) != 2: 
        await msg.reply("Исп: вклад [сумма] [дни]\n7,14,30,90,180,365")
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0], u['balance'])
    try: 
        d = int(args[1])
    except: 
        await msg.reply("❌ Неверный срок!")
        return
    if a <= 0: 
        await msg.reply("❌ Неверная сумма!")
        return
    res = core.bank.create_deposit(msg.from_user.id, a, d, u['balance'])
    if res['ok']: 
        core.db.update(msg.from_user.id, balance=u['balance'] - a)
    await msg.reply(res['msg'])

async def cmd_deposits(msg):
    if not is_private(msg): 
        return
    b = core.bank.get(msg.from_user.id)
    active = [d for d in b['deposits'] if d['status'] == 'active']
    if not active: 
        await msg.reply("📭 Нет активных вкладов")
        return
    text = "📈 **ВКЛАДЫ**\n\n"
    kb = []
    for d in active:
        end = datetime.datetime.fromisoformat(d['end_date'])
        left = (end - datetime.datetime.now()).days
        text += f"ID: `{d['id']}`\n💰 {fmt(d['amount'])} | 📈 {d['rate']}%\n⏰ {left} дн.\n\n"
        kb.append([InlineKeyboardButton(text=f"❌ Закрыть {d['id']}", callback_data=f"close_deposit_{d['id']}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_create_loan(msg, command):
    if not is_private(msg): 
        return
    args = command.args.split() if command.args else []
    if len(args) != 2: 
        await msg.reply("Исп: кредит [сумма] [дни]\n7,14,30,90,180,365")
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(args[0])
    try: 
        d = int(args[1])
    except: 
        await msg.reply("❌ Неверный срок!")
        return
    if a <= 0: 
        await msg.reply("❌ Неверная сумма!")
        return
    res = core.bank.create_loan(msg.from_user.id, a, d, u['balance'])
    if res['ok']: 
        core.db.update(msg.from_user.id, balance=u['balance'] + a)
    await msg.reply(res['msg'])

async def cmd_loans(msg):
    if not is_private(msg): 
        return
    b = core.bank.get(msg.from_user.id)
    active = [l for l in b['loans'] if l['status'] == 'active']
    if not active: 
        await msg.reply("📭 Нет активных кредитов")
        return
    text = "📉 **КРЕДИТЫ**\n\n"
    kb = []
    for l in active:
        end = datetime.datetime.fromisoformat(l['end_date'])
        left = (end - datetime.datetime.now()).days
        text += f"ID: `{l['id']}`\n💰 {fmt(l['amount'])} | 📈 {l['rate']}%\n💵 Осталось: {fmt(l['remaining'])}\n⏰ {left} дн.\n\n"
        kb.append([InlineKeyboardButton(text=f"💸 Оплатить {l['id']}", callback_data=f"pay_loan_{l['id']}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")])
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# === ПРОМОКОДЫ ===
async def cmd_create_promo(msg: Message, state: FSMContext):
    """Создать промокод"""
    u = core.db.get(msg.from_user.id)
    min_cost = MIN_PROMO_REWARD * MIN_PROMO_LIMIT
    
    if is_admin(msg.from_user.id):
        await state.set_state(PromoStates.waiting_reward)
        await state.update_data(step='reward')
        await msg.reply(
            f"🎫 **СОЗДАНИЕ ПРОМОКОДА (АДМИН)**\n\n"
            f"💰 Награда: {fmt(MIN_PROMO_REWARD)}-{fmt(MAX_PROMO_REWARD)}\n"
            f"👥 Лимит: {MIN_PROMO_LIMIT}-{MAX_PROMO_LIMIT}\n\n"
            f"Введите награду за использование:"
        )
    else:
        if u['balance'] < min_cost:
            await msg.reply(
                f"❌ Для создания промокода нужно минимум {fmt(min_cost)}\n"
                f"У вас {fmt(u['balance'])}"
            )
            return
        
        await state.set_state(PromoStates.waiting_reward)
        await state.update_data(step='reward')
        await msg.reply(
            f"🎫 **СОЗДАНИЕ ПРОМОКОДА**\n\n"
            f"💰 Награда: {fmt(MIN_PROMO_REWARD)}-{fmt(MAX_PROMO_REWARD)}\n"
            f"👥 Лимит: {MIN_PROMO_LIMIT}-{MAX_PROMO_LIMIT}\n"
            f"💎 С вас спишется: награда × лимит\n\n"
            f"Введите награду за использование:"
        )

async def process_promo(msg: Message, state: FSMContext):
    data = await state.get_data()
    step = data.get('step')
    
    if step == 'reward':
        a = core.parse_bet(msg.text)
        if a < MIN_PROMO_REWARD or a > MAX_PROMO_REWARD:
            await msg.reply(f"❌ Награда от {fmt(MIN_PROMO_REWARD)} до {fmt(MAX_PROMO_REWARD)}")
            return
        await state.update_data(reward=a, step='limit')
        await msg.reply(f"💰 Награда: {fmt(a)}\n\nВведите лимит использований (целое число от {MIN_PROMO_LIMIT} до {MAX_PROMO_LIMIT}):")
    
    elif step == 'limit':
        try:
            limit = int(msg.text.strip())
        except ValueError:
            await msg.reply(f"❌ Введите целое число от {MIN_PROMO_LIMIT} до {MAX_PROMO_LIMIT}!")
            return
        
        if limit < MIN_PROMO_LIMIT or limit > MAX_PROMO_LIMIT:
            await msg.reply(f"❌ Лимит должен быть от {MIN_PROMO_LIMIT} до {MAX_PROMO_LIMIT}!")
            return
        
        d = await state.get_data()
        total = d['reward'] * limit
        u = core.db.get(msg.from_user.id)
        
        is_admin_user = is_admin(msg.from_user.id)
        
        if is_admin_user:
            core.db.update(msg.from_user.id, balance=u['balance'])
        else:
            if u['balance'] < total:
                await msg.reply(f"❌ Нужно {fmt(total)} для создания промокода, у вас {fmt(u['balance'])}")
                await state.clear()
                return
            core.db.update(msg.from_user.id, balance=u['balance'] - total)
        
        res = core.promo.create(d['reward'], msg.from_user.id, limit)
        
        if res['ok']:
            if 'created_promocodes' not in u:
                u['created_promocodes'] = []
            u['created_promocodes'].append(res['code'])
            core.db.update(msg.from_user.id, created_promocodes=u['created_promocodes'])
            
            admin_note = " (бесплатно)" if is_admin_user else ""
            await msg.reply(
                f"✅ **Промокод создан!**{admin_note}\n\n"
                f"🎫 Код: `{res['code']}`\n"
                f"💰 Награда: {fmt(d['reward'])}\n"
                f"👥 Лимит: {limit}\n"
                f"💎 Общая стоимость: {fmt(total)}"
            )
            
            core.logs.add_log(
                admin_id=msg.from_user.id if is_admin_user else None,
                action="create_promo",
                details=f"Код: {res['code']} | Награда: {fmt(d['reward'])} | Лимит: {limit}"
            )
        else:
            if not is_admin_user:
                core.db.update(msg.from_user.id, balance=u['balance'])
            await msg.reply(res['msg'])
        
        await state.clear()

async def cmd_cancel_promo(msg: Message, state: FSMContext):
    """Отмена создания промокода"""
    current_state = await state.get_state()
    if current_state and current_state.startswith('PromoStates'):
        await state.clear()
        await msg.reply("❌ Создание промокода отменено")
    else:
        await msg.reply("❌ Нет активного процесса создания промокода")

async def cmd_my_promos(msg):
    u = core.db.get(msg.from_user.id)
    promos, used, claimed = core.promo.my_promos(msg.from_user.id)
    if not promos: 
        await msg.reply("📭 Вы не создавали промокоды")
        return
    text = f"🎫 **ВАШИ ПРОМОКОДЫ**\n\n📊 Статистика:\n• Всего: {len(promos)}\n• Использований: {used}\n• Выплачено: {fmt(claimed)}\n\n"
    for p in promos:
        exp = datetime.datetime.fromisoformat(p['expires'])
        days = (exp - datetime.datetime.now()).days
        text += f"🎫 `{p['code']}`\n   • {fmt(p['reward'])} | {p['used']}/{p['limit']}\n   • Осталось: {p['remaining']} | {days} дн.\n\n"
    await msg.reply(text)

async def cmd_promo(msg, command):
    if not command.args: 
        await msg.reply("Исп: промо КОД")
        return
    res = core.promo.use(command.args.upper().strip(), msg.from_user.id, core.db)
    await msg.reply(res['msg'])

# === АДМИН КОМАНДЫ ===
async def cmd_admin_give(msg: Message):
    """Выдать деньги (доступно всем админам)"""
    if not is_admin(msg.from_user.id) or not msg.reply_to_message:
        return
    
    parts = msg.text.lower().split()
    if len(parts) != 2:
        await msg.reply("Исп: выдать [сумма]")
        return
    
    a = core.parse_bet(parts[1])
    if a <= 0:
        await msg.reply("❌ Неверная сумма!")
        return
    
    uid = msg.reply_to_message.from_user.id
    u = core.db.get(uid)
    core.db.update(uid, balance=u['balance'] + a)
    
    core.logs.add_log(
        admin_id=msg.from_user.id,
        action="give",
        target_id=uid,
        amount=a
    )
    
    await msg.reply(f"✅ Выдано {fmt(a)} пользователю {msg.reply_to_message.from_user.full_name}")

async def cmd_admin_take(msg: Message):
    """Забрать деньги (доступно всем админам)"""
    if not is_admin(msg.from_user.id) or not msg.reply_to_message:
        return
    
    parts = msg.text.lower().split()
    if len(parts) != 2:
        await msg.reply("Исп: забрать [сумма]")
        return
    
    a = core.parse_bet(parts[1])
    if a <= 0:
        await msg.reply("❌ Неверная сумма!")
        return
    
    uid = msg.reply_to_message.from_user.id
    u = core.db.get(uid)
    if u['balance'] < a:
        await msg.reply(f"❌ У пользователя только {fmt(u['balance'])}")
        return
    
    core.db.update(uid, balance=u['balance'] - a)
    
    core.logs.add_log(
        admin_id=msg.from_user.id,
        action="take",
        target_id=uid,
        amount=a
    )
    
    await msg.reply(f"✅ Забрано {fmt(a)} у пользователя {msg.reply_to_message.from_user.full_name}")

async def cmd_admin_give_status(msg: Message, command: CommandObject):
    """Выдать статус (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    if not msg.reply_to_message:
        await msg.reply("❌ Ответьте на сообщение пользователя!")
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 1:
        statuses = core.status.all()
        text = "📋 **Доступные статусы:**\n\n"
        for status_id, status in statuses.items():
            text += f"• {status['emoji']} {status['name']} (ID: {status_id})\n"
        text += "\nИспользование: `выдать статус [название статуса]`"
        await msg.reply(text, parse_mode="Markdown")
        return
    
    status_name = ' '.join(args).strip()
    recipient_id = msg.reply_to_message.from_user.id
    
    status_id, status = core.status.get_status_by_name(status_name)
    
    if not status_id:
        await msg.reply(f"❌ Статус '{status_name}' не найден!")
        return
    
    res = core.status.admin_give_status(recipient_id, status_id, core.db)
    
    if res['ok']:
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="give_status",
            target_id=recipient_id,
            details=f"Статус: {status['name']}"
        )
        
        await msg.reply(res['msg'])
        try:
            await msg.bot.send_message(
                recipient_id,
                f"👑 Админ выдал вам статус {status['emoji']} {status['name']}!"
            )
        except:
            pass
    else:
        await msg.reply(res['msg'])

# === КОМАНДЫ УПРАВЛЕНИЯ АДМИНАМИ ===
async def cmd_make_admin(msg: Message):
    """Назначить админа (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    if not msg.reply_to_message:
        await msg.reply("❌ Ответьте на сообщение пользователя!")
        return
    
    target_id = msg.reply_to_message.from_user.id
    target_name = msg.reply_to_message.from_user.full_name
    
    res = core.admins.add_admin(target_id, msg.from_user.id)
    
    if res['ok']:
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="make_admin",
            target_id=target_id
        )
        
        await msg.reply(res['msg'])
        try:
            await msg.bot.send_message(
                target_id,
                f"👑 Вас назначили администратором!\n\n"
                f"Админ: {msg.from_user.full_name}"
            )
        except:
            pass
    else:
        await msg.reply(res['msg'])

async def cmd_remove_admin(msg: Message):
    """Снять админа (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    if not msg.reply_to_message:
        await msg.reply("❌ Ответьте на сообщение пользователя!")
        return
    
    target_id = msg.reply_to_message.from_user.id
    
    res = core.admins.remove_admin(target_id, msg.from_user.id)
    
    if res['ok']:
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="remove_admin",
            target_id=target_id
        )
        
        await msg.reply(res['msg'])
        try:
            await msg.bot.send_message(
                target_id,
                f"👋 Вас сняли с должности администратора."
            )
        except:
            pass
    else:
        await msg.reply(res['msg'])

async def cmd_admins(msg: Message):
    """Список всех админов"""
    if not is_admin(msg.from_user.id):
        return
    
    admins = core.admins.get_all_admins()
    
    if not admins:
        await msg.reply("📭 Нет администраторов")
        return
    
    text = "👑 **СПИСОК АДМИНИСТРАТОРОВ**\n\n"
    
    for uid, info in admins.items():
        try:
            chat = await msg.bot.get_chat(int(uid))
            name = chat.first_name
            if chat.last_name:
                name += f" {chat.last_name}"
        except:
            name = f"ID {uid}"
        
        role = "👑 СОЗДАТЕЛЬ" if info.get("is_creator") else "🛡️ АДМИН"
        added_by = f" | Назначил: {info.get('added_by', 'Неизвестно')}" if not info.get("is_creator") else ""
        added_at = info.get('added_at', 'Неизвестно')[:10]
        
        text += f"{role} — {name}\n"
        text += f"   🆔 {uid}\n"
        text += f"   📅 с {added_at}{added_by}\n\n"
    
    await msg.reply(text)

# === КОМАНДЫ ДЛЯ РАБОТЫ С ЛОГАМИ ===
async def cmd_logs(msg: Message):
    """Просмотр логов (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    parts = msg.text.lower().split()
    admin_filter = None
    action_filter = None
    
    if len(parts) > 1:
        if parts[1].isdigit():
            admin_filter = int(parts[1])
        else:
            action_filter = parts[1]
    
    logs = core.logs.get_logs(limit=50, admin_id=admin_filter, action=action_filter)
    
    kb = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="logs_stats")],
        [InlineKeyboardButton(text="🧹 Очистить логи", callback_data="logs_clear_confirm")]
    ]
    
    text = core.logs.format_logs(logs, detailed=True)
    
    if admin_filter:
        text = f"🔍 Фильтр по админу: {admin_filter}\n\n" + text
    if action_filter:
        text = f"🔍 Фильтр по действию: {action_filter}\n\n" + text
    
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def cmd_logs_stats(msg: Message):
    """Статистика по логам (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    stats = core.logs.get_stats()
    
    text = "📊 **СТАТИСТИКА ДЕЙСТВИЙ АДМИНОВ**\n\n"
    text += f"📋 Всего действий: {stats['total_actions']}\n"
    text += f"⏰ За 24 часа: {stats['last_24h']}\n\n"
    
    text += "💰 **Финансы:**\n"
    text += f"   💸 Выдано всего: {fmt(stats['total_given'])}\n"
    text += f"   💰 Забрано всего: {fmt(stats['total_taken'])}\n"
    text += f"   ⛔ Забанено: {stats['total_bans']}\n\n"
    
    text += "📌 **По действиям:**\n"
    action_names = {
        "give": "💰 Выдача денег",
        "take": "💸 Забирание денег",
        "ban": "⛔ Бан",
        "unban": "✅ Разбан",
        "make_admin": "👑 Назначение админа",
        "remove_admin": "👤 Снятие админа",
        "give_status": "⭐ Выдача статуса",
        "create_promo": "🎫 Создание промокода",
        "create_nft": "🖼️ Создание NFT",
        "clear_logs": "🧹 Очистка логов"
    }
    
    for action, count in stats['by_action'].items():
        name = action_names.get(action, action)
        text += f"   {name}: {count}\n"
    
    text += "\n👤 **По админам:**\n"
    for admin, count in stats['by_admin'].items():
        try:
            chat = await msg.bot.get_chat(int(admin))
            name = chat.first_name
            if chat.last_name:
                name += f" {chat.last_name}"
        except:
            name = f"ID {admin}"
        text += f"   {name}: {count}\n"
    
    await msg.reply(text)

# === КОМАНДА СОЗДАНИЯ НОВОГО NFT ===
async def cmd_create_nft(msg: Message, state: FSMContext):
    """Создать новый NFT (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    await state.set_state(AdminStates.waiting_nft_id)
    await msg.reply(
        "🖼️ **СОЗДАНИЕ НОВОГО NFT**\n\n"
        "Введите ID товара (английскими буквами, без пробелов):\n"
        "Например: `golden_pepe` или `diamond_ring`\n\n"
        "❗ ID должен быть уникальным и использоваться в командах"
    )

async def process_nft_id(msg: Message, state: FSMContext):
    nft_id = msg.text.strip()
    
    if not re.match(r'^[a-zA-Z0-9_]+$', nft_id):
        await msg.reply("❌ ID может содержать только латинские буквы, цифры и символ подчеркивания!\nПопробуйте снова:")
        return
    
    items = core.shop.items()
    if nft_id in items:
        await msg.reply("❌ Товар с таким ID уже существует! Введите другой ID:")
        return
    
    await state.update_data(nft_id=nft_id)
    await state.set_state(AdminStates.waiting_nft_name)
    await msg.reply("✅ ID принят!\n\nВведите название NFT (можно на русском):")

async def process_nft_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    
    if len(name) > 50:
        await msg.reply("❌ Название слишком длинное! Максимум 50 символов.\nВведите другое название:")
        return
    
    await state.update_data(nft_name=name)
    await state.set_state(AdminStates.waiting_nft_price)
    await msg.reply(
        "✅ Название принято!\n\n"
        "Введите цену NFT:\n"
        "Можно использовать формат: 1000, 5к, 1кк, 10ккк и т.д."
    )

async def process_nft_price(msg: Message, state: FSMContext):
    price = core.parse_bet(msg.text)
    
    if price <= 0:
        await msg.reply("❌ Неверная цена! Введите положительное число:")
        return
    
    if price > 1000000000000:
        await msg.reply("❌ Цена слишком большая! Максимум 1кккк (1,000,000,000,000)\nВведите другую цену:")
        return
    
    await state.update_data(nft_price=price)
    await state.set_state(AdminStates.waiting_nft_quantity)
    await msg.reply(
        f"✅ Цена: {fmt(price)}\n\n"
        "Введите количество NFT для продажи:\n"
        "(можно оставить 0, если хотите сделать NFT редким)"
    )

async def process_nft_quantity(msg: Message, state: FSMContext):
    try:
        quantity = int(msg.text.strip())
        if quantity < 0:
            await msg.reply("❌ Количество не может быть отрицательным!\nВведите число:")
            return
        if quantity > 10000:
            await msg.reply("❌ Слишком много! Максимум 10,000 NFT\nВведите другое число:")
            return
    except ValueError:
        await msg.reply("❌ Введите целое число!")
        return
    
    await state.update_data(nft_quantity=quantity)
    await state.set_state(AdminStates.waiting_nft_description)
    await msg.reply(
        "✅ Количество принято!\n\n"
        "Введите описание NFT (можно оставить пустым, отправив `-`):"
    )

async def process_nft_description(msg: Message, state: FSMContext):
    description = msg.text.strip()
    
    if description == '-':
        description = "Нет описания"
    
    if len(description) > 200:
        await msg.reply("❌ Описание слишком длинное! Максимум 200 символов.\nВведите другое описание:")
        return
    
    await state.update_data(nft_description=description)
    await state.set_state(AdminStates.waiting_nft_emoji)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁", callback_data="emoji_🎁"),
         InlineKeyboardButton(text="💎", callback_data="emoji_💎"),
         InlineKeyboardButton(text="👑", callback_data="emoji_👑")],
        [InlineKeyboardButton(text="⚡", callback_data="emoji_⚡"),
         InlineKeyboardButton(text="🔥", callback_data="emoji_🔥"),
         InlineKeyboardButton(text="⭐", callback_data="emoji_⭐")],
        [InlineKeyboardButton(text="🎮", callback_data="emoji_🎮"),
         InlineKeyboardButton(text="💰", callback_data="emoji_💰"),
         InlineKeyboardButton(text="💊", callback_data="emoji_💊")],
        [InlineKeyboardButton(text="🖼️ Свой вариант", callback_data="emoji_custom")]
    ])
    
    await msg.reply(
        "✅ Описание принято!\n\n"
        "Выберите эмодзи для NFT или нажмите 'Свой вариант' чтобы ввести вручную:",
        reply_markup=kb
    )

async def process_nft_emoji(msg: Message, state: FSMContext):
    emoji = msg.text.strip()
    
    if len(emoji) > 10:
        await msg.reply("❌ Это не похоже на эмодзи! Введите один эмодзи:")
        return
    
    await finish_nft_creation(msg, state, emoji)

async def finish_nft_creation(msg: Message, state: FSMContext, emoji: str):
    data = await state.get_data()
    
    nft_id = data.get('nft_id')
    name = data.get('nft_name')
    price = data.get('nft_price')
    quantity = data.get('nft_quantity')
    description = data.get('nft_description')
    
    success = core.shop.add(nft_id, name, price, quantity, description, emoji)
    
    if success:
        core.logs.add_log(
            admin_id=msg.from_user.id,
            action="create_nft",
            details=f"Создан NFT: {nft_id} | {name} | Цена: {fmt(price)} | Кол-во: {quantity}"
        )
        
        text = f"✅ **NFT УСПЕШНО СОЗДАН!**\n\n"
        text += f"🆔 ID: `{nft_id}`\n"
        text += f"{emoji} **{name}**\n"
        text += f"💰 Цена: {fmt(price)}\n"
        text += f"📦 Количество: {quantity}\n"
        text += f"📝 Описание: {description}\n\n"
        text += f"Теперь игроки могут купить его в магазине (`нфт`)"
        
        await msg.reply(text)
    else:
        await msg.reply(f"❌ Ошибка при создании NFT! Возможно, ID `{nft_id}` уже существует.")
    
    await state.clear()

async def cmd_all_nft(msg: Message):
    """Показать все NFT в магазине (только создатель)"""
    if not is_creator(msg.from_user.id):
        return
    
    items = core.shop.items()
    
    if not items:
        await msg.reply("📭 В магазине нет NFT")
        return
    
    text = "🖼️ **ВСЕ NFT В МАГАЗИНЕ**\n\n"
    
    for item_id, item in items.items():
        emoji = item.get('emoji', '🎁')
        name = item.get('name', 'Без названия')
        price = item.get('price', 0)
        quantity = item.get('quantity', 0)
        sold = item.get('sold', 0)
        
        text += f"{emoji} **{name}**\n"
        text += f"   🆔 `{item_id}`\n"
        text += f"   💰 {fmt(price)} | 📦 {quantity} | 📊 {sold} продано\n\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 3500):
            await msg.reply(text[i:i+3500])
    else:
        await msg.reply(text)

# === ИГРЫ ===
async def cmd_coin(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        choice = args[1].lower().replace('ё','е')
        if choice not in ['орел','решка']: 
            await msg.reply("❌ Выберите 'орел' или 'решка'")
            return
        res = core.games.coin(msg.from_user.id, bet, choice)
        if res['win']: 
            await msg.reply(f"🎉 {msg.from_user.first_name}, выпал {res['res']}! +{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
        else: 
            await msg.reply(f"😞 {msg.from_user.first_name}, выпал {res['res']}! -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🦅 Орел", callback_data=f"coin_{bet}_орел"), InlineKeyboardButton(text="🪙 Решка", callback_data=f"coin_{bet}_решка")]])
        await msg.reply(f"💰 Ставка: {fmt(bet)}\nВыберите сторону:", reply_markup=kb)
    else: 
        await msg.reply("Исп: монетка СТАВКА [орел/решка]")

async def cmd_slots(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        res = core.games.slots(msg.from_user.id, bet)
        if res['win']: 
            await msg.reply(f"🎰 {msg.from_user.first_name}, {' | '.join(res['reels'])}\n🎉 ДЖЕКПОТ x{res['mult']}! +{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
        else: 
            await msg.reply(f"🎰 {msg.from_user.first_name}, {' | '.join(res['reels'])}\n😞 Проигрыш: -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    else: 
        await msg.reply("Исп: слоты СТАВКА")

async def cmd_dice(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        try: 
            pred = int(args[1])
        except: 
            await msg.reply("❌ Введите число от 1 до 6")
            return
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        if pred < 1 or pred > 6: 
            await msg.reply("❌ Число от 1 до 6!")
            return
        res = core.games.dice(msg.from_user.id, bet, pred)
        if res['win']: 
            await msg.reply(f"🎲 {msg.from_user.first_name}, выпало {res['roll']}! +{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
        else: 
            await msg.reply(f"🎲 {msg.from_user.first_name}, выпало {res['roll']}! -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(1,4)],
                                                   [InlineKeyboardButton(text=str(i), callback_data=f"dice_{bet}_{i}") for i in range(4,7)]])
        await msg.reply(f"💰 Ставка: {fmt(bet)}\nВыберите число:", reply_markup=kb)
    else: 
        await msg.reply("Исп: кубик СТАВКА ЧИСЛО")

async def cmd_crash(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 2:
        bet = core.parse_bet(args[0], u['balance'])
        try: 
            target = float(args[1].replace(',','.'))
        except: 
            await msg.reply("❌ Неверный множитель!")
            return
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        if target < 1.1 or target > 100: 
            await msg.reply("❌ Множитель от 1.1 до 100")
            return
        res = core.crash.start(msg.from_user.id, bet, target)
        if res['win']: 
            await msg.reply(f"🚀 {msg.from_user.first_name}, КРАШ! x{res['crash']}!\n✅ Выигрыш: +{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
        else: 
            await msg.reply(f"💥 {msg.from_user.first_name}, КРАШ! x{res['crash']}...\n❌ Проигрыш: -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
    elif len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1.5x", callback_data=f"crash_{bet}_1.5"), InlineKeyboardButton(text="2x", callback_data=f"crash_{bet}_2"), InlineKeyboardButton(text="3x", callback_data=f"crash_{bet}_3")],
            [InlineKeyboardButton(text="5x", callback_data=f"crash_{bet}_5"), InlineKeyboardButton(text="10x", callback_data=f"crash_{bet}_10"), InlineKeyboardButton(text="20x", callback_data=f"crash_{bet}_20")]
        ])
        await msg.reply(f"🚀 КРАШ\n💰 Ставка: {fmt(bet)}\nВыберите множитель:", reply_markup=kb)
    else: 
        await msg.reply("Исп: краш СТАВКА [иксы]")

async def cmd_mines(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        mines = int(args[1]) if len(args) > 1 else 3
        
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        
        if mines < 1 or mines > 6: 
            await msg.reply("❌ Количество мин должно быть от 1 до 6!")
            return
        
        res = core.mines.start(msg.from_user.id, bet, mines)
        if not res['ok']: 
            await msg.reply(res['msg'])
            return
        
        await msg.reply(
            f"🎮 **МИНЫ** | 💣 {mines} мин\n"
            f"💰 Ставка: {fmt(bet)}\n"
            f"📈 x1.0 | 💎 0\n\n"
            f"Выбирайте клетки:",
            reply_markup=core.mines.kb(msg.from_user.id, res['data']['field'])
        )
    else: 
        await msg.reply("🎮 **МИНЫ**\n\nИспользование: `мины СТАВКА [КОЛ-ВО МИН]`\n\nПримеры:\n• `мины 1000 3` - 3 мины\n• `мины все 5` - 5 мин\n• `мины 5000` - 3 мины (по умолчанию)\n\n💣 Количество мин: от 1 до 6")

async def cmd_tower(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 1:
        bet = core.parse_bet(args[0], u['balance'])
        mines = int(args[1]) if len(args) > 1 else 1
        
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        
        if mines < 1 or mines > 4: 
            await msg.reply("❌ Количество мин на этаже должно быть от 1 до 4!")
            return
        
        res = core.tower.start(msg.from_user.id, bet, mines)
        if not res['ok']: 
            await msg.reply(res['msg'])
            return
        
        mults = core.tower.mults(mines)
        max_mult = mults[-1]
        
        await msg.reply(
            f"🏗️ **БАШНЯ** | Этаж 1/9 | 💣 {mines} мин на этаже\n"
            f"💰 Ставка: {fmt(bet)}\n"
            f"📈 Макс множитель: x{max_mult}\n\n"
            f"Выберите клетку:",
            reply_markup=core.tower.kb(msg.from_user.id, res['data'])
        )
    else: 
        await msg.reply(
            "🏗️ **БАШНЯ**\n\n"
            "Использование: `башня СТАВКА [КОЛ-ВО МИН]`\n\n"
            "**Множители:**\n"
            "• 1 мина: x1.2 → x1.5 → x2.0 → x2.5 → x3.2 → x4.0 → x5.0 → x6.0 → x7.0\n"
            "• 2 мины: x1.7 → x2.1 → x2.8 → x3.5 → x4.5 → x5.6 → x7.0 → x8.4 → x9.8\n"
            "• 3 мины: x2.2 → x2.7 → x3.6 → x4.5 → x5.8 → x7.2 → x9.0 → x10.8 → x12.6\n"
            "• 4 мины: x2.6 → x3.3 → x4.4 → x5.5 → x7.0 → x8.8 → x11.0 → x13.2 → x15.4\n\n"
            "Примеры:\n"
            "• `башня 1000 1` - 1 мина\n"
            "• `башня все 3` - 3 мины на этаже"
        )

async def cmd_roulette(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) >= 2:
        bet = core.parse_bet(args[0], u['balance'])
        btype = args[1].lower()
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        type_map = {'чет':'even','нечет':'odd','even':'even','odd':'odd','красное':'red','red':'red','чёрное':'black','black':'black',
                   '1-12':'1-12','13-24':'13-24','25-36':'25-36','зеро':'zero','zero':'zero'}
        val = None
        if btype in type_map: 
            btype = type_map[btype]
        else:
            try:
                val = int(btype)
                if 0 <= val <= 36: 
                    btype = 'number'
                else: 
                    await msg.reply("❌ Неверный тип ставки!")
                    return
            except: 
                await msg.reply("❌ Неверный тип ставки!")
                return
        res = core.roulette.play(msg.from_user.id, bet, btype, val)
        color_emoji = '🟢' if res['color'] == 'green' else ('🔴' if res['color'] == 'red' else '⚫')
        if res['win']: 
            await msg.reply(f"🎰 {msg.from_user.first_name}, РУЛЕТКА\n\nВыпало: {color_emoji} {res['num']}\n\n✅ ВЫИГРЫШ! x{res['mult']}\n💰 +{fmt(res['amount'])}\n💵 Баланс: {fmt(res['balance'])}")
        else: 
            await msg.reply(f"🎰 {msg.from_user.first_name}, РУЛЕТКА\n\nВыпало: {color_emoji} {res['num']}\n\n❌ ПРОИГРЫШ\n💸 -{fmt(res['amount'])}\n💵 Баланс: {fmt(res['balance'])}")
    else: 
        await msg.reply("🎰 **РУЛЕТКА**\n\nТипы: чет/нечет, красное/черное, 1-12,13-24,25-36, зеро, число (0-36)\nПример: рулетка 1000 чет")

async def cmd_gold(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        
        chat_id = msg.chat.id
        
        res = core.gold.start(msg.from_user.id, bet, chat_id)
        if not res['ok']: 
            await msg.reply(res['msg'])
            return
        
        await msg.reply(
            f"{core.gold.display(res['data'])}\n\n💰 Ставка: {fmt(bet)}\n🎯 0/12 | 📈 1x\n💎 Выберите сторону:",
            reply_markup=core.gold.kb(msg.from_user.id, res['data'])
        )
    else:
        await msg.reply("🎰 **ЗОЛОТО**\n\nПравила: 50/50, множители растут\nИсп: золото СТАВКА")

async def cmd_risk(msg, command):
    args = command.args.split() if command.args else []
    u = core.db.get(msg.from_user.id)
    if len(args) == 1:
        bet = core.parse_bet(args[0], u['balance'])
        if bet <= 0 or bet > u['balance']: 
            await msg.reply(f"❌ Неверная ставка! Баланс: {fmt(u['balance'])}")
            return
        
        chat_id = msg.chat.id
        
        res = core.risk.start(msg.from_user.id, bet, chat_id)
        if not res['ok']: 
            await msg.reply(res['msg'])
            return
        
        await msg.reply(
            f"{core.risk.display(res['data'])}\n\n💎 Выберите клетку:",
            reply_markup=core.risk.kb(msg.from_user.id, res['data'])
        )
    else:
        await msg.reply("🎲 **РИСК**\n\nПравила: 6 клеток, 3 выигрышных, 3 проигрышных\nИсп: риск СТАВКА")

# === ПЕРЕВОДЫ ДЕНЕГ ===
async def cmd_give(msg):
    if not msg.reply_to_message: 
        await msg.reply("❌ Ответьте на сообщение получателя!")
        return
    to_id = msg.reply_to_message.from_user.id
    from_id = msg.from_user.id
    if from_id == to_id: 
        await msg.reply("❌ Себе нельзя!")
        return
    parts = msg.text.lower().split()
    if len(parts) != 2 or parts[0] not in ['дать','дай']: 
        await msg.reply("Исп: дать [сумма]")
        return
    sender = core.db.get(from_id)
    a = core.parse_bet(parts[1], sender['balance'])
    if a <= 0: 
        await msg.reply("❌ Неверная сумма!")
        return
    if sender['balance'] < a: 
        await msg.reply(f"❌ Недостаточно! Баланс: {fmt(sender['balance'])}")
        return
    core.db.update(from_id, balance=sender['balance'] - a)
    core.db.update(to_id, balance=core.db.get(to_id)['balance'] + a)
    await msg.reply(f"✅ Переведено {fmt(a)} пользователю {msg.reply_to_message.from_user.full_name}")

# === ОБРАБОТЧИК КНОПОК ===
async def callback_handler(cb: CallbackQuery, state: FSMContext):
    data = cb.data
    uid = cb.from_user.id
    chat_id = cb.message.chat.id
    
    try:
        if data == "ignore":
            await cb.answer()
            return
        
        # === СТАТУСЫ ===
        if data.startswith('status_view_'):
            status_id = data[12:]
            statuses = core.status.all()
            status = statuses.get(status_id)
            if not status:
                await cb.answer("❌ Статус не найден", show_alert=True)
                return
            
            user = core.db.get(uid)
            
            kb = []
            if user['status'] != status_id and user['balance'] >= status['price']:
                kb.append([InlineKeyboardButton(text="💳 Купить", callback_data=f"status_buy_{status_id}")])
            kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="status_back")])
            
            await cb.message.edit_text(
                f"{status['emoji']} **{status['name']}**\n\n"
                f"💰 Цена: {fmt(status['price'])}\n"
                f"🎁 Бонус: {fmt(status['min_bonus'])} - {fmt(status['max_bonus'])} (каждый час)\n"
                f"⏰ Кулдаун: 1 час\n\n"
                f"📝 {status['description']}\n\n"
                f"💳 Ваш баланс: {fmt(user['balance'])}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                parse_mode="Markdown"
            )
        
        elif data.startswith('status_buy_'):
            status_id = data[11:]
            res = core.status.buy(uid, status_id, core.db)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await cmd_status_shop(cb.message)
        
        elif data == "status_back":
            await cmd_status_shop(cb.message)
        
        # === МОНЕТКА ===
        elif data.startswith('coin_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, choice = int(parts[1]), parts[2]
                res = core.games.coin(uid, bet, choice)
                if res['win']:
                    await cb.message.edit_text(f"🎉 {cb.from_user.first_name}, выпал {res['res']}! +{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
                else:
                    await cb.message.edit_text(f"😞 {cb.from_user.first_name}, выпал {res['res']}! -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
        
        # === КУБИК ===
        elif data.startswith('dice_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, num = int(parts[1]), int(parts[2])
                res = core.games.dice(uid, bet, num)
                if res['win']:
                    await cb.message.edit_text(f"🎲 {cb.from_user.first_name}, выпало {res['roll']}! +{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
                else:
                    await cb.message.edit_text(f"🎲 {cb.from_user.first_name}, выпало {res['roll']}! -{fmt(res['amount'])}\n💰 {fmt(res['balance'])}")
        
        # === КРАШ ===
        elif data.startswith('crash_'):
            parts = data.split('_')
            if len(parts) == 3:
                bet, target = int(parts[1]), float(parts[2])
                res = core.crash.start(uid, bet, target)
                if res['ok']:
                    if res['win']:
                        await cb.message.edit_text(f"🚀 {cb.from_user.first_name}, КРАШ! Ракета улетела на x{res['crash']}!\n✅ Выигрыш: +{fmt(res['amount'])}\n💰 Баланс: {fmt(res['balance'])}")
                    else:
                        await cb.message.edit_text(f"💥 {cb.from_user.first_name}, КРАШ! Ракета улетела на x{res['crash']}...\n❌ Проигрыш: -{fmt(res['amount'])}\n💰 Баланс: {fmt(res['balance'])}")
        
        # === МИНЫ ===
        elif data.startswith('mines_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, r, c = int(parts[1]), int(parts[2]), int(parts[3])
                if uid != user_id: 
                    await cb.answer("❌ Не ваша игра!", show_alert=True)
                    return
                res = core.mines.open(user_id, r, c)
                if not res['ok']: 
                    await cb.answer(res['msg'], show_alert=True)
                    return
                if res.get('over'):
                    await cb.message.edit_text(f"💥 БУМ! Проигрыш: {fmt(res['bet'])}\n🎯 Открыто: {res['opened']}", reply_markup=core.mines.kb(user_id, res['field'], False))
                else:
                    game = core.mines.games.get(user_id)
                    if game:
                        await cb.message.edit_text(f"🎮 Мины | 💣 {game['count']}\n💰 {fmt(game['bet'])}\n🎯 {res['opened']}/{res['max']} | 📈 x{res['mult']:.2f}\n💎 {fmt(res['won'])}", reply_markup=core.mines.kb(user_id, res['field']))
        
        elif data.startswith('cashout_'):
            user_id = int(data.split('_')[1])
            if uid != user_id: 
                await cb.answer("❌ Не ваша игра!", show_alert=True)
                return
            res = core.mines.cashout(user_id)
            if not res['ok']: 
                await cb.answer(res['msg'], show_alert=True)
                return
            await cb.message.edit_text(f"🏆 Выигрыш: +{fmt(res['won'])}\n🎯 {res['opened']} | 📈 x{res['mult']:.2f}\n💰 Баланс: {fmt(res['balance'])}", reply_markup=core.mines.kb(user_id, res['field'], False))
        
        elif data == "mines_new":
            await cb.message.edit_text("🎮 Используй: мины СТАВКА [МИН]")
        
        # === БАШНЯ ===
        elif data.startswith('tower_'):
            if data.startswith('tower_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id: 
                    await cb.answer("❌ Не ваша игра!", show_alert=True)
                    return
                res = core.tower.cashout(user_id)
                if not res['ok']: 
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(f"🏆 Вы забрали! +{fmt(res['won'])}\n📈 x{res['mult']:.1f}\n🎯 Этажей: {res['rows']}\n💰 Баланс: {fmt(res['balance'])}")
            else:
                parts = data.split('_')
                if len(parts) == 4:
                    user_id, r, c = int(parts[1]), int(parts[2]), int(parts[3])
                    if uid != user_id: 
                        await cb.answer("❌ Не ваша игра!", show_alert=True)
                        return
                    res = core.tower.open(user_id, r, c)
                    if not res['ok']: 
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    if res.get('over'):
                        if res.get('mine'):
                            kb = [[InlineKeyboardButton(text=res['row_data']['cells'][c], callback_data="ignore") for c in range(5)]]
                            await cb.message.edit_text(f"💥 БУМ! Проигрыш: {fmt(res['bet'])}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
                        else:
                            await cb.message.edit_text(f"🏆 МАКСИМУМ! +{fmt(res['won'])}\n📈 x{res['mult']:.1f}\n🎯 {res['rows']} этажей\n💰 Баланс: {fmt(res['balance'])}")
                    else:
                        game = core.tower.games.get(user_id)
                        if game:
                            await cb.message.edit_text(f"🏗️ Башня | Этаж {game['row']+1}/9 | 💣 {game['mines']}\n💰 {fmt(game['bet'])}\n📈 x{res['mult']:.1f} | 💎 {fmt(res['won'])}", reply_markup=core.tower.kb(user_id, game))
        
        # === ЗОЛОТО ===
        elif data.startswith('gold_'):
            if data.startswith('gold_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id: 
                    await cb.answer("❌ Не ваша игра!", show_alert=True)
                    return
                res = core.gold.cashout(user_id, chat_id)
                if not res['ok']: 
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(f"🏆 Вы забрали! +{fmt(res['won'])}\n📈 x{res['mult']}\n🎯 {res['level']}/12\n💰 Баланс: {fmt(res['balance'])}")
            else:
                side = 1 if 'left' in data else 2
                user_id = int(data.split('_')[2])
                if uid != user_id: 
                    await cb.answer("❌ Не ваша игра!", show_alert=True)
                    return
                res = core.gold.choose(user_id, side, chat_id)
                if not res['ok']: 
                    await cb.answer(res['msg'], show_alert=True)
                    return
                if res.get('max', False):
                    await cb.message.edit_text(f"🏆 МАКСИМУМ! +{fmt(res['won'])}\n📈 x{res['mult']}\n🎯 {res['level']}/12\n💰 Баланс: {fmt(res['balance'])}")
                elif res.get('game_over', False):
                    game_data = {'bet': res['bet'], 'level': res['level'], 'history': [{'level': res['level']+1, 'choice': res['choice'], 'money': res['money'], 'win': False}]}
                    await cb.message.edit_text(core.gold.display(game_data, res))
                else:
                    game = core.gold.games.get(user_id)
                    if game:
                        await cb.message.edit_text(f"{core.gold.display(game, res)}\n\n💰 {fmt(game['bet'])}\n🎯 {game['level']}/12 | 📈 x{res['mult']}\n💎 Выберите сторону:", reply_markup=core.gold.kb(user_id, game))
        
        # === РИСК ===
        elif data.startswith('risk_'):
            if data.startswith('risk_cash_'):
                user_id = int(data.split('_')[2])
                if uid != user_id: 
                    await cb.answer("❌ Не ваша игра!", show_alert=True)
                    return
                res = core.risk.cashout(user_id, chat_id)
                if not res['ok']: 
                    await cb.answer(res['msg'], show_alert=True)
                    return
                await cb.message.edit_text(f"🏆 Вы забрали! +{fmt(res['won'])}\n📈 Сумма множителей: x{res['total_mult']:.2f}\n🎯 {res['level']}/3\n💰 Баланс: {fmt(res['balance'])}")
            elif data.startswith('risk_cell_'):
                parts = data.split('_')
                if len(parts) >= 4:
                    user_id = int(parts[2])
                    idx = int(parts[3])
                    if uid != user_id: 
                        await cb.answer("❌ Не ваша игра!", show_alert=True)
                        return
                    res = core.risk.open(user_id, idx, chat_id)
                    if not res['ok']: 
                        await cb.answer(res['msg'], show_alert=True)
                        return
                    if res.get('max'):
                        await cb.message.edit_text(f"🏆 МАКСИМУМ! Вы открыли все клетки!\n+{fmt(res['won'])}\n📈 Сумма множителей: x{res['total_mult']:.2f}\n💰 Баланс: {fmt(res['balance'])}")
                    elif res.get('game_over'):
                        await cb.message.edit_text("💥 Ты нашел мину! Проигрыш!")
                    else:
                        game = core.risk.games.get(user_id)
                        if game:
                            await cb.message.edit_text(f"{core.risk.display(game)}\n\n✅ Выигрыш: +{fmt(res['won'])}", reply_markup=core.risk.kb(user_id, game))
        
        # === БАНК ===
        elif data.startswith('bank_') or data.startswith('close_deposit_') or data.startswith('pay_loan_'):
            if data == "bank_card":
                b = core.bank.get(uid)
                kb = [[InlineKeyboardButton(text="💰 Положить", callback_data="bank_card_deposit"), InlineKeyboardButton(text="💸 Снять", callback_data="bank_card_withdraw")],
                      [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]]
                await cb.message.edit_text(f"💳 **КАРТА**\n\nБаланс: {fmt(b['card_balance'])}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
            elif data == "bank_deposits":
                await cmd_deposits(cb.message)
            elif data == "bank_loans":
                await cmd_loans(cb.message)
            elif data == "bank_help":
                kb = [[InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]]
                await cb.message.edit_text("🏦 **ПОМОЩЬ**\n\n💳 Карта - скрытый счет\n📈 Вклады - пассивный доход\n📉 Кредиты - 7/14 дней, до 5кк", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
            elif data == "bank_back":
                await cmd_bank(cb.message)
            elif data.startswith("close_deposit_"):
                dep_id = data[14:]
                res = core.bank.close_deposit(uid, dep_id)
                if res['ok']:
                    user = core.db.get(uid)
                    core.db.update(uid, balance=user['balance'] + res['amount'])
                    await cb.answer("✅ Вклад закрыт", show_alert=True)
                    await cmd_deposits(cb.message)
                else:
                    await cb.answer(res['msg'], show_alert=True)
            elif data.startswith("pay_loan_"):
                loan_id = data[9:]
                await state.update_data(pay_loan_id=loan_id)
                await state.set_state(BankStates.waiting_loan_payment)
                await cb.message.edit_text("💸 Введите сумму для оплаты:")
        
        # === МОИ НФТ ===
        elif data.startswith('nft_page_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, page = parts[2], int(parts[3])
                if str(uid) != user_id:
                    await cb.answer("❌ Это не ваш инвентарь!", show_alert=True)
                    return
                await show_nft_list(cb, user_id, page)
        
        elif data.startswith('nft_view_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, unique_id = parts[2], '_'.join(parts[3:])
                if str(uid) != user_id:
                    await cb.answer("❌ Это не ваш NFT!", show_alert=True)
                    return
                await show_nft_detail(cb, user_id, unique_id)
        
        elif data.startswith('nft_back_'):
            user_id = data.split('_')[2]
            if str(uid) != user_id:
                await cb.answer("❌ Это не ваш инвентарь!", show_alert=True)
                return
            await show_nft_list(cb, user_id, 0)
        
        elif data.startswith('nft_sell_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, unique_id = parts[2], '_'.join(parts[3:])
                if str(uid) != user_id:
                    await cb.answer("❌ Это не ваш NFT!", show_alert=True)
                    return
                await state.update_data(sell_nft_id=unique_id)
                await state.set_state(MarketStates.waiting_price)
                await cb.message.edit_text("💰 Введите цену для продажи NFT:")
        
        elif data.startswith('nft_transfer_start_'):
            parts = data.split('_')
            if len(parts) >= 5:
                user_id, unique_id = parts[3], '_'.join(parts[4:])
                if str(uid) != user_id:
                    await cb.answer("❌ Это не ваш NFT!", show_alert=True)
                    return
                
                await state.update_data(transfer_nft_id=unique_id)
                await state.set_state(TransferNFTStates.waiting_user)
                await cb.message.edit_text(
                    "👤 Введите ID пользователя, которому хотите передать NFT (только цифры):\n\n"
                    "❌ Отмена: /cancel"
                )
        
        # === ПЕРЕДАЧА NFT ===
        elif data.startswith('transfer_page_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, page = parts[2], int(parts[3])
                if str(uid) != user_id:
                    await cb.answer("❌ Это не ваш инвентарь!", show_alert=True)
                    return
                await show_nft_for_transfer(cb, state, user_id, page)
        
        elif data.startswith('transfer_select_'):
            parts = data.split('_')
            if len(parts) >= 4:
                user_id, unique_id = parts[2], '_'.join(parts[3:])
                if str(uid) != user_id:
                    await cb.answer("❌ Это не ваш NFT!", show_alert=True)
                    return
                await process_transfer_nft(cb, state, user_id, unique_id)
        
        elif data.startswith('transfer_confirm_'):
            parts = data.split('_')
            if len(parts) >= 4:
                to_uid, unique_id = parts[2], '_'.join(parts[3:])
                await confirm_transfer_nft(cb, state, to_uid, unique_id)
        
        elif data == "transfer_cancel":
            await state.clear()
            await cb.message.edit_text("❌ Передача отменена")
        
        # === МАГАЗИН НФТ ===
        elif data.startswith('shop_page_'):
            page = int(data.split('_')[2])
            await show_shop_list(uid, cb, page)
        
        elif data.startswith('shop_view_'):
            item_id = data[10:]
            await show_shop_item(cb, item_id)
        
        elif data.startswith('shop_buy_'):
            item_id = data[9:]
            res = core.shop.buy(item_id, uid, core.db)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await show_shop_item(cb, item_id)
        
        elif data == "shop_back":
            await show_shop_list(uid, cb, 0)
        
        # === РЫНОК ===
        elif data.startswith('market_page_'):
            page = int(data.split('_')[2])
            await show_market_list(uid, cb, page)
        
        elif data.startswith('market_view_'):
            listing_id = int(data.split('_')[2])
            await show_market_listing(cb, listing_id)
        
        elif data.startswith('market_buy_'):
            listing_id = int(data.split('_')[2])
            res = core.market.buy_listing(listing_id, uid)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await show_market_list(uid, cb, 0)
            else:
                await show_market_listing(cb, listing_id)
        
        elif data.startswith('market_cancel_'):
            listing_id = int(data.split('_')[2])
            res = core.market.cancel_listing(listing_id, uid)
            await cb.answer(res['msg'], show_alert=True)
            if res['ok']:
                await show_market_list(uid, cb, 0)
            else:
                await show_market_listing(cb, listing_id)
        
        elif data == "market_back":
            await show_market_list(uid, cb, 0)
        
        elif data == "market_refresh":
            await show_market_list(uid, cb, 0)
        
        # === ЛОГИ ===
        elif data == "logs_stats":
            if not is_creator(uid):
                await cb.answer("❌ Только создатель!", show_alert=True)
                return
            
            stats = core.logs.get_stats()
            
            text = "📊 **СТАТИСТИКА ДЕЙСТВИЙ АДМИНОВ**\n\n"
            text += f"📋 Всего действий: {stats['total_actions']}\n"
            text += f"⏰ За 24 часа: {stats['last_24h']}\n\n"
            
            text += "💰 **Финансы:**\n"
            text += f"   💸 Выдано всего: {fmt(stats['total_given'])}\n"
            text += f"   💰 Забрано всего: {fmt(stats['total_taken'])}\n"
            text += f"   ⛔ Забанено: {stats['total_bans']}\n\n"
            
            text += "📌 **По действиям:**\n"
            action_names = {
                "give": "💰 Выдача денег",
                "take": "💸 Забирание денег",
                "ban": "⛔ Бан",
                "unban": "✅ Разбан",
                "make_admin": "👑 Назначение админа",
                "remove_admin": "👤 Снятие админа",
                "give_status": "⭐ Выдача статуса",
                "create_promo": "🎫 Создание промокода",
                "create_nft": "🖼️ Создание NFT",
                "clear_logs": "🧹 Очистка логов"
            }
            
            for action, count in stats['by_action'].items():
                name = action_names.get(action, action)
                text += f"   {name}: {count}\n"
            
            kb = [[InlineKeyboardButton(text="◀️ Назад к логам", callback_data="logs_back")]]
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        
        elif data == "logs_clear_confirm":
            if not is_creator(uid):
                await cb.answer("❌ Только создатель!", show_alert=True)
                return
            
            kb = [
                [InlineKeyboardButton(text="✅ Да, очистить", callback_data="logs_clear_yes")],
                [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="logs_back")]
            ]
            await cb.message.edit_text(
                "⚠️ **ВНИМАНИЕ!**\n\nВы действительно хотите очистить все логи?\nЭто действие нельзя отменить!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )
        
        elif data == "logs_clear_yes":
            if not is_creator(uid):
                await cb.answer("❌ Только создатель!", show_alert=True)
                return
            
            core.logs.clear_logs()
            core.logs.add_log(
                admin_id=uid,
                action="clear_logs",
                details="Очистил все логи через кнопку"
            )
            
            await cb.message.edit_text("🧹 Все логи успешно очищены!")
            await cb.answer()
        
        elif data == "logs_back":
            if not is_creator(uid):
                await cb.answer("❌ Только создатель!", show_alert=True)
                return
            
            logs = core.logs.get_logs()
            text = core.logs.format_logs(logs, detailed=True)
            
            kb = [
                [InlineKeyboardButton(text="📊 Статистика", callback_data="logs_stats")],
                [InlineKeyboardButton(text="🧹 Очистить логи", callback_data="logs_clear_confirm")]
            ]
            
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        
        # === СОЗДАНИЕ NFT ===
        elif data.startswith('emoji_'):
            if data == "emoji_custom":
                await state.set_state(AdminStates.waiting_nft_emoji)
                await cb.message.edit_text(
                    "Введите свой эмодзи для NFT (можно отправить один символ или эмодзи):"
                )
            else:
                emoji = data[6:]
                await finish_nft_creation(cb.message, state, emoji)
            await cb.answer()
        
        await cb.answer()
    except Exception as e:
        print(f"Error in callback_handler: {e}")
        await cb.answer("❌ Произошла ошибка", show_alert=True)

# === ОБРАБОТЧИК ОПЛАТЫ КРЕДИТА ===
async def handle_loan_payment(msg: Message, state: FSMContext):
    if msg.text.lower() == '/cancel': 
        await state.clear()
        await msg.reply("❌ Отменено")
        return
    data = await state.get_data()
    loan_id = data.get('pay_loan_id')
    if not loan_id: 
        await state.clear()
        return
    u = core.db.get(msg.from_user.id)
    a = core.parse_bet(msg.text, u['balance'])
    if a <= 0: 
        await msg.reply("❌ Неверная сумма!")
        return
    res = core.bank.pay_loan(msg.from_user.id, loan_id, a, u['balance'])
    if res['ok']:
        core.db.update(msg.from_user.id, balance=u['balance'] - a)
        await msg.reply(res['msg'])
        await state.clear()
        await cmd_loans(msg)
    else: 
        await msg.reply(res['msg'])

# === ОБРАБОТЧИК ПРОДАЖИ НА РЫНКЕ ===
async def handle_market_price(msg: Message, state: FSMContext):
    if msg.text.lower() == '/cancel': 
        await state.clear()
        await msg.reply("❌ Отменено")
        return
    
    data = await state.get_data()
    nft_id = data.get('sell_nft_id')
    if not nft_id:
        await state.clear()
        return
    
    uid = str(msg.from_user.id)
    inventory = core.shop.inventory(uid)
    nft = next((item for item in inventory if item['unique_id'] == nft_id), None)
    
    if not nft:
        await msg.reply("❌ NFT не найден!")
        await state.clear()
        return
    
    price = core.parse_bet(msg.text)
    if price <= 0:
        await msg.reply("❌ Введите положительную цену!")
        return
    
    res = core.market.add_listing(msg.from_user.id, nft, price)
    await msg.reply(res['msg'])
    
    if res['ok']:
        await show_nft_list(msg, uid, 0)
    
    await state.clear()

# === РУССКИЕ КОМАНДЫ ===
async def handle_russian(msg: Message, state: FSMContext):
    text = msg.text.lower().strip()
    
    class FC: 
        def __init__(self, a): 
            self.args = a
        def __bool__(self): 
            return self.args is not None
    
    if text in ['баланс', 'б']: 
        await cmd_balance(msg)
    elif text in ['профиль', 'проф', 'п']:
        await cmd_profile(msg)
    elif text in ['помощь', 'help', 'команды']: 
        await cmd_help(msg)
    elif text == 'топ': 
        await cmd_top(msg)
    elif text == 'топ статусы': 
        await cmd_top_status(msg)
    elif text == 'банк': 
        await cmd_bank(msg)
    elif text == 'карта': 
        await cmd_card(msg)
    elif text == 'вклады': 
        await cmd_deposits(msg)
    elif text == 'кредиты': 
        await cmd_loans(msg)
    elif text == 'создать промо': 
        await cmd_create_promo(msg, state)
    elif text == 'мои промо': 
        await cmd_my_promos(msg)
    elif text == 'игры': 
        await cmd_games(msg)
    elif text == '/cancel_game': 
        await cmd_cancel_game(msg)
    elif text == 'статус': 
        await cmd_status(msg)
    elif text == 'бонус': 
        await cmd_bonus(msg)
    elif text == 'статусы': 
        await cmd_status_shop(msg)
    elif text in ['мои нфт', 'инвентарь']:
        await cmd_my_nft(msg)
    elif text in ['нфт', 'магазин']:
        await cmd_nft_shop(msg)
    elif text == 'рынок':
        await cmd_market(msg)
    elif text.startswith('передать нфт '):
        await cmd_transfer_nft_start(msg, state)
    elif text == 'ид' and msg.reply_to_message:
        await cmd_id(msg)
    elif text.startswith('бан ') and msg.reply_to_message and is_admin(msg.from_user.id):
        await cmd_ban(msg, state)
    elif text.startswith('разбан') and is_admin(msg.from_user.id):
        await cmd_unban(msg)
    elif text.startswith('топ общий') and is_admin(msg.from_user.id):
        await cmd_total_balance(msg)
    elif text == 'админы' and is_admin(msg.from_user.id):
        await cmd_admins(msg)
    elif text.startswith('назначить') and msg.reply_to_message and is_creator(msg.from_user.id):
        await cmd_make_admin(msg)
    elif text.startswith('снять') and msg.reply_to_message and is_creator(msg.from_user.id):
        await cmd_remove_admin(msg)
    elif text == 'логи' and is_creator(msg.from_user.id):
        await cmd_logs(msg)
    elif text.startswith('логи ') and is_creator(msg.from_user.id):
        await cmd_logs(msg)
    elif text == 'статистика' and is_creator(msg.from_user.id):
        await cmd_logs_stats(msg)
    elif text.startswith('создать нфт') and is_creator(msg.from_user.id):
        await cmd_create_nft(msg, state)
    elif text.startswith('все нфт') and is_creator(msg.from_user.id):
        await cmd_all_nft(msg)
    elif text == '/cancel' or text == 'отмена':
        await cmd_cancel_transfer(msg, state)
    elif text == '/cancel_promo' or text == 'отмена промо':
        await cmd_cancel_promo(msg, state)
    
    elif text.startswith('положить '): 
        p = text.split()
        await cmd_deposit(msg, FC(p[1] if len(p) > 1 else None))
    elif text.startswith('снять '): 
        p = text.split()
        await cmd_withdraw(msg, FC(p[1] if len(p) > 1 else None))
    elif text.startswith('вклад '): 
        p = text.split()
        if len(p) >= 3:
            await cmd_create_deposit(msg, FC(f"{p[1]} {p[2]}"))
        else:
            await msg.reply("Исп: вклад [сумма] [дни]")
    elif text.startswith('кредит '): 
        p = text.split()
        if len(p) >= 3:
            await cmd_create_loan(msg, FC(f"{p[1]} {p[2]}"))
        else:
            await msg.reply("Исп: кредит [сумма] [дни]")
    elif text.startswith('монетка'): 
        p = text.split()
        if len(p) > 1:
            await cmd_coin(msg, FC(' '.join(p[1:])))
        else:
            await cmd_coin(msg, FC(None))
    elif text.startswith('слоты'): 
        p = text.split()
        if len(p) > 1:
            await cmd_slots(msg, FC(p[1]))
        else:
            await cmd_slots(msg, FC(None))
    elif text.startswith('кубик'): 
        p = text.split()
        if len(p) > 1:
            await cmd_dice(msg, FC(' '.join(p[1:])))
        else:
            await cmd_dice(msg, FC(None))
    elif text.startswith('краш'): 
        p = text.split()
        if len(p) > 1:
            await cmd_crash(msg, FC(' '.join(p[1:])))
        else:
            await cmd_crash(msg, FC(None))
    elif text.startswith('мины'): 
        p = text.split()
        if len(p) > 1:
            await cmd_mines(msg, FC(' '.join(p[1:])))
        else:
            await cmd_mines(msg, FC(None))
    elif text.startswith('башня'): 
        p = text.split()
        if len(p) > 1:
            await cmd_tower(msg, FC(' '.join(p[1:])))
        else:
            await cmd_tower(msg, FC(None))
    elif text.startswith('рулетка') or text.startswith('рул'): 
        p = text.split()
        if len(p) > 1:
            await cmd_roulette(msg, FC(' '.join(p[1:])))
        else:
            await cmd_roulette(msg, FC(None))
    elif text.startswith('золото'): 
        p = text.split()
        if len(p) > 1:
            await cmd_gold(msg, FC(p[1]))
        else:
            await cmd_gold(msg, FC(None))
    elif text.startswith('риск'): 
        p = text.split()
        if len(p) > 1:
            await cmd_risk(msg, FC(p[1]))
        else:
            await cmd_risk(msg, FC(None))
    elif text.startswith('промо '): 
        code = text[6:].strip().upper()
        await cmd_promo(msg, CommandObject(args=code))
    elif text.startswith('дать ') or text.startswith('дай '): 
        await cmd_give(msg)
    elif text.startswith('выдать '): 
        if 'статус' in text:
            parts = text.split()
            if len(parts) >= 3:
                status_name = ' '.join(parts[2:])
                await cmd_admin_give_status(msg, CommandObject(args=status_name))
            else:
                await cmd_admin_give_status(msg, CommandObject(args=''))
        else:
            await cmd_admin_give(msg)
    elif text.startswith('забрать '): 
        await cmd_admin_take(msg)

# === ЗАПУСК ===
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.message.middleware.register(ban_middleware)
    
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_games, Command("games"))
    dp.message.register(cmd_cancel_game, Command("cancel_game"))
    
    for cmd in ['balance', 'profile', 'top', 'top_status', 'bank', 'card', 'deposits', 'loans', 
                'my_promos', 'status', 'bonus', 'status_shop', 'my_nft', 'nft_shop', 'market',
                'admins', 'logs', 'logs_stats', 'all_nft']:
        dp.message.register(globals()[f"cmd_{cmd}"], Command(cmd))
    
    for cmd in ['deposit', 'withdraw', 'create_deposit', 'create_loan', 'coin', 'slots', 
                'dice', 'crash', 'mines', 'tower', 'roulette', 'gold', 'risk', 'promo', 
                'create_promo', 'give']:
        dp.message.register(globals()[f"cmd_{cmd}"], Command(cmd))
    
    for cmd in ['admin_give', 'admin_take', 'admin_give_status', 'make_admin', 'remove_admin',
                'ban', 'unban', 'total_balance', 'create_nft']:
        dp.message.register(globals()[f"cmd_{cmd}"], Command(cmd))
    
    dp.message.register(cmd_id, Command("id"))
    dp.message.register(cmd_cancel_transfer, Command("cancel"))
    dp.message.register(cmd_cancel_promo, Command("cancel_promo"))
    
    dp.message.register(handle_transfer_user_input, TransferNFTStates.waiting_user)
    dp.message.register(process_promo, PromoStates.waiting_reward)
    dp.message.register(process_promo, PromoStates.waiting_limit)
    dp.message.register(handle_loan_payment, BankStates.waiting_loan_payment)
    dp.message.register(handle_market_price, MarketStates.waiting_price)
    
    dp.message.register(process_nft_id, AdminStates.waiting_nft_id)
    dp.message.register(process_nft_name, AdminStates.waiting_nft_name)
    dp.message.register(process_nft_price, AdminStates.waiting_nft_price)
    dp.message.register(process_nft_quantity, AdminStates.waiting_nft_quantity)
    dp.message.register(process_nft_description, AdminStates.waiting_nft_description)
    dp.message.register(process_nft_emoji, AdminStates.waiting_nft_emoji)
    
    dp.message.register(handle_russian, F.text)
    dp.callback_query.register(callback_handler)
    
    print("✅ Бот запущен!")
    print("✅ Система админов и логов работает!")
    print("✅ Статусы и бонусы работают!")
    print("✅ NFT система работает!")
    print("✅ Рынок работает!")
    print("✅ Передача NFT работает!")
    print("✅ Профиль (п) работает везде!")
    print("✅ NFT команды только в ЛС!")
    print("✅ Система банов работает!")
    print("✅ Команда ID работает!")
    print("✅ Топ по общему балансу работает!")
    print("✅ Игры сбалансированы: мины (1-6 мин), башня (макс x7 для 1 мины)")
    print("✅ Админы не участвуют в рейтингах")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try: 
        asyncio.run(main())
    except KeyboardInterrupt: 
        print("\n❌ Бот остановлен")
    except Exception as e: 
        print(f"\n❌ Ошибка: {e}")


