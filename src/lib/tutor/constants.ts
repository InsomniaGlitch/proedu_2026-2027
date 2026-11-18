export const COURSE_NAME =
  process.env.NEXT_PUBLIC_COURSE_NAME || "Устойчивое развитие: системный подход";

export const MAX_MESSAGE_LENGTH = 4000;
export const DEFAULT_CHAT_TITLE = "Новый чат";

export const MAX_CHATS = 50;
export const MAX_MESSAGES_PER_CHAT = 300;

export const SUGGESTIONS = [
  "Объясни, что такое ESG",
  "С чего начать работу над кейсом?",
  "Какие материалы курса помогут разобраться в системном подходе?",
  "Помоги составить план самостоятельной работы",
];

export const GREETING = `Привет! Я ваш ИИ-помощник по курсу «${COURSE_NAME}».

Я могу ответить на вопросы по материалам курса, объяснить условия заданий, подсказать, где искать нужные материалы, и помочь спланировать работу над кейсом.

Я не выполняю задания за вас и не выставляю оценки.

Чем могу помочь?`;
