# Band Monitor

 *( Playwright �ѧ Band }�p��� Python y�

## ��y'

- &��
- �{U Band &�
- {UEs��� Ͱ{U	
- � 10 �ѧ}�p��
- RESTful API ��
- //��\bѧ

## ���L

### 1. �ŝV

```bash
# n��� UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# ��y�V
uv sync

# �� Playwright O�h
uv run playwright install
```

### 2. /��

```bash
# �L�h
uv run run.py
```

�h( http://localhost:8000 /�

### 3. API �c

/���� http://localhost:8000/docs � Swagger API �c

## API ��

### ��&�
```bash
POST /accounts
{
    "username": "your_email@example.com",
    "password": "your_password"
}
```

### ��@	&�
```bash
GET /accounts
```

### ���&�
```bash
GET /accounts/{account_id}
```

### /�ѧ
```bash
POST /accounts/{account_id}/start
```

### �\ѧ
```bash
POST /accounts/{account_id}/pause
```

### bѧ
```bash
POST /accounts/{account_id}/resume
```

###  d&�
```bash
DELETE /accounts/{account_id}
```

## (�

1. **��&�**: ( POST /accounts ���� Band &�
2. **/�ѧ**: ( POST /accounts/{id}/start /��&��ѧ
3. **��**: ( GET /accounts/{id} �&���}�p�
4. **�\/b**: (����6ѧ�

## y'�

- **�E**: O�h��X( `browser_sessions/` �Us���/� Ͱ{U
- **�ѧ**: � 10 ��7�}�hubv�U}�p�
- **&�/**: ��ѧ* Band &�
- **��**: / running/paused/stopped 	�ѧ�