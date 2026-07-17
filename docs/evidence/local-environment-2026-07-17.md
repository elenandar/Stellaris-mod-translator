# Локальное окружение — evidence 2026-07-17

Это датированный read-only inventory для планирования M1, а не постоянное обещание совместимости. При сборе не запускалась ни одна модель, не устанавливались пакеты и не менялась конфигурация Ollama или игры.

## Компьютер и игра

| Параметр | Наблюдаемое значение |
|---|---|
| Архитектура | Apple Silicon `arm64` |
| macOS | `26.5.2` (`25F84`) |
| Память | 51 539 607 552 байта (48 GiB) |
| Stellaris | `Pegasus v4.4.6 (fdde)`, raw `v4.4.6` |
| Официальная локализация | 231 английский и 233 русских `.yml`-файла |
| Workshop inventory | 114 каталогов модов; 62 содержат каталог `localisation` |
| Developer tools | выбраны Command Line Tools; полный Xcode не выбран |

Числа описывают этот компьютер на указанную дату. Названия модов и тексты локализации в репозитории не сохраняются.

## Установленные инструменты

| Инструмент | Наблюдаемое значение |
|---|---|
| Ollama | `0.32.1` |
| SQLite | `3.51.0` |
| Node.js | `26.4.0` |
| npm | `11.17.0` |
| pnpm | `11.9.0` |
| Rust/Cargo | не найдены в `PATH` |

Node.js присутствует в общем локальном окружении, а не как зависимость CLI baseline. Установка и pinning Rust — отдельная будущая M1-задача; M0R ничего не устанавливает.

## Состояние Ollama

- Доступно 13 локальных tags с сохранённым размером от 13 до 21 GB.
- `ollama ps` не показывает загруженных моделей.
- Ни один tag inventory не оканчивается на `-cloud`.
- Loopback API сам по себе не считается доказательством local residency; контракт приложения всё равно проверяет tag, full digest, local weights, endpoint и redirects.
- Project-level local-only enforcement ещё не реализован. M1 threat work обязан добавить fail-closed проверки и не полагаться на ambient configuration.

### Inventory

| Tag | Полный digest | Размер |
|---|---|---:|
| `deepseek-r1-32b-64k:latest` | `34854015def7a0acb498ddb5869addd8feeb1df4b9a8e58bc8aa8b72a224c9b0` | 19 GB |
| `deepseek-r1:32b` | `edba8017331d15236e57480eb45406c0d721db77a4cdcf234df500fc2ad3960c` | 19 GB |
| `gpt-oss-20b-64k:latest` | `e325453613b5d1623678fe4176a37bbc4538d76f61396b98b781f5105b18be08` | 13 GB |
| `qwen3-coder-30b-64k:latest` | `7650fe393b4bdff90b9de0c6fb4552ef2c08688eabf13e9f10428a5adcc27772` | 18 GB |
| `glm47-flash-64k:latest` | `eda0d22a00c9ad329d36eb5e694aeb0f51135e589ee6a0ee2725dd8691c94209` | 19 GB |
| `qwen3-coder:30b` | `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca` | 18 GB |
| `glm-4.7-flash:latest` | `4475827791a269b02c8ec49b1c3bc1abb5846bacf3fae015b75d33986322d8f6` | 19 GB |
| `qwen36-35b-coding-32k:latest` | `01831f661515b26c2413319f959fcc29d746cf75a69ba23572427c56e7d3e99f` | 21 GB |
| `qwen36-27b-coding-32k:latest` | `dfef24fbe925e076092ff0865d27afff8a4eafbd4cb8e8b9f756c274c91471bb` | 19 GB |
| `gpt-oss-20b-32k:latest` | `0490a76f4bd5e28b8e4a8f319f693aa193a76f46d719f1bdc78b6f1df0591c04` | 13 GB |
| `qwen3.6:27b-coding-nvfp4` | `42a2d9de99b0e72ab7022637dd3f8ee3103e116e4b287901080b7c9c9cc0ee66` | 19 GB |
| `qwen3.6:35b-a3b-coding-nvfp4` | `cd2692a833e66c4c98991b67e9fbaa0bb15a93285baac9240c022f2f40075b6d` | 21 GB |
| `gpt-oss:20b` | `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7` | 13 GB |

## Первые кандидаты на переводческий benchmark

| Tag | Размер параметров | Quantization | Контекст модели | Наблюдаемые defaults tag |
|---|---:|---|---:|---|
| `glm47-flash-64k:latest` | 29.9B | Q4_K_M | 202 752 | `num_ctx=65536`, `temperature=0.2` |
| `deepseek-r1-32b-64k:latest` | 32.8B | Q4_K_M | 131 072 | `num_ctx=65536`, `temperature=0.6` |
| `gpt-oss-20b-64k:latest` | 20.9B | не указана | 131 072 | `num_ctx=65536`, `temperature=0.2` |

Эти три general-модели входят в M1B. Coding-focused Qwen tags не являются начальным translation baseline. M1B явно задаёт общий контекст 8–16K и сопоставимые параметры, сохраняет полный digest и не изменяет active localisation files.

## Ограничения evidence

- Inventory может измениться после обновления или pull; каждый benchmark заново записывает полный digest.
- Наличие tag не доказывает качество перевода, structured-output reliability или соответствие residency policy.
- Число файлов не доказывает coverage формата.
- Полные официальные и mod-localisation тексты остаются вне Git и требуют corpus/provenance policy в M1.
