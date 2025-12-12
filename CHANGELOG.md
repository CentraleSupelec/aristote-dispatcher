# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.2] - 2025-12-10

### Added
- 📊 Add `user_organization`  and `server_organization` to usage metrics in database (#55)

### Fixed
- 🩹 Removed the foreign key to users in metrics table (#55)

## [1.4.1] - 2025-12-10

### Added
- 📊 Add `routing_mode` to usage metrics in database (#53)
- ✨ Enhanced user management CLI tools (#53)

## [1.4.0] - 2025-10-06

### Added
- ✨ Local priority to enable the user to prioritize vllm instances of its organization (#38)
- ✨ Default local priority mode set in user token (#46)
- ✨ Users can now degrade their own priority (useful for testing purposes) (#40)
- ✨ Script to handily create users/tokens in the cluster (#41)
- ✨ Add new requeue policy compatible with round-robin routing strategy (#47)

### Changed
- ♻️ Clean code (imports) and changed projects structure (#47)
- 🗃️ Manage database with migrations (using `alembic`) (#47)

### Fixed
- 🩹 Counter for current concurrent requests in a vllm instance is now automatically decremented after some time, to fix
a bug where decrements are missed (#42)

## [1.3.1] - 2025-08-05

### Fixed
- 🩹 Add information in requeue policy log message (#39)

## [1.3.0] - 2025-07-25

### Added
- ✨ Ping remote LLM servers regularly and exclude them (if possible) if they are not healthy (#31)
- ✨ Add control on the maximum number of simultaneous requests handled by the gateway, with requeue support for extra requests until remote LLM servers are available (#37)

## [1.2.13]

### Added
- ✨ Feature to transfer priority to inference server
- ✨ Policy concept to handle requests after server choice
- 📊 Usage metrics

### Fixed
- 🐛 Least busy strategy

## [1.2.4]

### Fixed
- 🩹 Workers/Consumers: Load balancing

### New Contributors
- 👤 @blanch0t made their first contribution in #12

## [1.2.3]

### Added
- ✨ Workers/Consumers: Connect to a vLLM protected by a token
- ✨ Workers/Consumers: Consumer checks vLLM queue

### Fixed
- 🩹 Workers/Consumers: Hide AMQ queue appearing as model

### New Contributors
- 👤 @mohamedalibarkailluin made their first contribution in #13

## [1.1.1]

### Added
- ✨ Workers: Unprivileged user

### Fixed
- 🩹 Workers/Consumers: Changes to logging
- 🩹 Sender: Hide requests body by default
- 🩹 Workers/Consumers: Add `QueueExpiration` entry in values.yaml
- 🩹 Helm chart: Add `.gitignore` in `helm_charts/charts`
- 🩹 Helm chart: Fix typo in pod-monitor templating

### Documentation
- 📖 Update docs

### New Contributors
- 👤 @matthieucharreire made their first contribution in #1  
- 👤 @emilejaf made their first contribution in #5  
- 👤 @mathisbot made their first contribution in #6
