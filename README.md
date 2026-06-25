# 편집몬 재택 공고 → 텔레그램 알림 (24시간 자동)

편집몬(editmon.com) **'편집자 모집'** 게시판에 새 공고가 올라오면, **재택근무 가능 공고만** 골라
핵심 내용(제목·회사·급여·경력·근무형태·편집툴·복리후생·마감)과 링크를 텔레그램으로 보내줍니다.

GitHub Actions(깃허브 클라우드)에서 30분마다 자동 실행되므로 **내 컴퓨터를 꺼도 24시간 동작**합니다.

- 받는 봇: **@Editmon_bot** (이미 연결됨)
- 확인 주기: **30분마다**
- 필터: **재택 가능 공고만** (모든 공고로 바꾸려면 아래 '설정 바꾸기' 참고)

---

## 준비물

1. **GitHub 계정** (없으면 https://github.com 에서 무료 가입)
2. **텔레그램 봇 토큰** — @BotFather에서 받은 `8893...` 형태의 토큰
   (이미 발급해 두셨습니다. 잃어버렸으면 BotFather에서 `/token`으로 다시 확인)

---

## 설치 (한 번만, 약 5분)

### 1. 새 저장소(Repository) 만들기
- GitHub 우측 상단 **+** → **New repository**
- 이름: 예) `editmon-alert`
- **반드시 Private(비공개)** 선택 → **Create repository**

### 2. 파일 3개 올리기
이 폴더(`editmon-alert`) 안의 파일을 저장소에 그대로 올립니다.
가장 쉬운 방법: 저장소 첫 화면의 **"uploading an existing file"** 링크 클릭 →
아래 파일들을 끌어다 놓기 → **Commit changes**

```
monitor.py
state.json
.github/workflows/monitor.yml   ← .github/workflows 폴더 구조 그대로 유지
```

> `.github/workflows/` 폴더 구조가 중요합니다. 드래그 업로드가 폴더를 유지하지 못하면,
> **Add file → Create new file**에서 파일 이름 칸에 `.github/workflows/monitor.yml`를
> 그대로 입력하면 폴더가 자동으로 만들어집니다.

### 3. 봇 토큰을 비밀(Secret)로 등록
- 저장소 **Settings** → 왼쪽 **Secrets and variables** → **Actions**
- **New repository secret**
  - Name: `TELEGRAM_BOT_TOKEN`
  - Secret: (BotFather에서 받은 봇 토큰 붙여넣기)
- **Add secret**

> 토큰은 코드/파일에 넣지 않고 여기 Secret에만 넣습니다. 그래서 안전합니다.

### 4. 쓰기 권한 켜기 (중복 발송 방지용 상태 저장)
- **Settings** → **Actions** → **General**
- 맨 아래 **Workflow permissions** → **Read and write permissions** 선택 → **Save**

### 5. 첫 실행 (기준선 설정)
- 상단 **Actions** 탭 → (안내가 나오면) 워크플로 **활성화(Enable)**
- 왼쪽 **"편집몬 재택 공고 알림"** 클릭 → 오른쪽 **Run workflow** → **Run workflow**
- 1~2분 뒤 텔레그램으로 **"🤖 편집몬 재택 공고 알림 시작!"** 메시지가 오면 성공.

이후에는 **30분마다 자동**으로 새 재택 공고가 올라올 때만 메시지가 옵니다.

---

## 동작 방식

- 매 실행마다 '편집자 모집' 목록을 읽고, **마지막으로 확인한 글번호(watermark)보다 큰 새 공고**만 처리합니다.
- 새 공고는 상세페이지를 열어 **복리후생/근무형태에 '재택'이 있는 공고만** 발송합니다.
- 처리한 마지막 글번호는 `state.json`에 자동 저장(커밋)되어 **같은 공고를 두 번 보내지 않습니다.**
- 첫 실행은 과거 공고를 쏟아내지 않도록 **기준선만 잡고** 시작 메시지 한 번만 보냅니다.

---

## 설정 바꾸기

**`.github/workflows/monitor.yml`** 파일을 수정하면 됩니다.

- **모든 새 공고 받기**(재택 외 포함): `ONLY_REMOTE` 값을 `"0"`으로
  ```yaml
  ONLY_REMOTE: "0"
  ```
- **확인 주기 변경**: `cron` 값 수정 (예: 매시간 → `"0 * * * *"`, 15분마다 → `"*/15 * * * *"`)
- **다른 텔레그램으로 받기**: `TELEGRAM_CHAT_ID` 값을 바꾸기
  (단, 받는 사람이 먼저 @Editmon_bot에게 메시지를 한 번 보내야 합니다)

---

## 잠깐 멈추거나 끄기
- **Actions** 탭 → 왼쪽 **"편집몬 재택 공고 알림"** → 오른쪽 **··· → Disable workflow**
- 다시 켜려면 같은 자리에서 **Enable workflow**

---

## 문제 해결

- **메시지가 안 와요**
  - Actions 탭에서 최근 실행이 빨간 X면 클릭해 로그 확인.
  - `send FAILED` 또는 토큰 오류면 Secret(`TELEGRAM_BOT_TOKEN`) 값 확인.
  - @Editmon_bot을 차단했거나 대화를 지웠다면 다시 **시작(Start)**.
- **`state.json` 커밋 실패 / 같은 공고가 반복 발송**
  - 4번(Read and write permissions) 설정을 다시 확인하세요.
- **시간이 정확히 30분 간격이 아니에요**
  - GitHub의 예약 실행은 혼잡 시 수 분~십수 분 지연될 수 있습니다(정상). 누락분은 다음 실행에서 함께 처리됩니다.
- **갑자기 차단(빈 결과)돼요**
  - 편집몬이 차단 방식을 바꾸면 멈출 수 있습니다. 그때 알려주시면 수집 방식을 업데이트합니다.

---

생성: Claude (Cowork) · 수집은 공개된 '편집자 모집' 목록만 사용합니다.
