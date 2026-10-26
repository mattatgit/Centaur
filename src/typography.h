#pragma once

// Call once after constructing QGuiApplication, before creating QML engines.
// Each native process registers its own bundled fonts.
bool initializeTypography();
