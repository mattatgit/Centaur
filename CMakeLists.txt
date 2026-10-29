cmake_minimum_required(VERSION 3.22)
project(Centaur VERSION 0.3.1 LANGUAGES CXX)
set(CENTAUR_BUILD_ID "dev" CACHE STRING "Source revision identifying this Centaur build")
if(APPLE)
    set(CMAKE_OSX_DEPLOYMENT_TARGET "14.4")
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
include(CTest)
set(CENTAUR_NETWORK_EXECUTABLE "" CACHE FILEPATH "Prebuilt native centaur-network helper")
if(CENTAUR_NETWORK_EXECUTABLE)
    add_custom_target(centaur-network-helper ALL
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CENTAUR_NETWORK_EXECUTABLE}" "${CMAKE_CURRENT_BINARY_DIR}/centaur-network")
    install(PROGRAMS "${CENTAUR_NETWORK_EXECUTABLE}" DESTINATION bin)
endif()

find_package(Qt6 6.8 REQUIRED COMPONENTS Core Gui Quick QuickControls2 Network Svg)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    find_package(Qt6 REQUIRED COMPONENTS WaylandCompositor)
    set(PREVIEW_QML qml/WaylandPreview.qml)
else()
    set(PREVIEW_QML qml/PreviewUnavailable.qml)
endif()
add_library(centaur_typography STATIC src/typography.cpp src/typography.h)
target_link_libraries(centaur_typography PUBLIC Qt6::Gui Qt6::Qml)
target_include_directories(centaur_typography PUBLIC src)
qt_add_resources(centaur_typography fonts PREFIX "/fonts" BASE assets/fonts/inter FILES
    assets/fonts/inter/Inter-Regular.ttf
    assets/fonts/inter/Inter-SemiBold.ttf
    assets/fonts/inter/Inter-Bold.ttf
    assets/fonts/inter/LICENSE.txt)
qt_add_resources(centaur_typography tight_fonts PREFIX "/fonts" BASE assets/fonts/inter-tight FILES
    assets/fonts/inter-tight/InterTight-Variable.ttf
    assets/fonts/inter-tight/OFL.txt)
add_library(centaur_core STATIC
    src/workspace.cpp src/workspace.h
    src/session.cpp src/session.h
    src/collaboration.cpp src/collaboration.h
    src/irohbridge.cpp src/irohbridge.h
    src/agent.cpp src/agent.h
    src/controller.cpp src/controller.h
    src/svgicon.cpp src/svgicon.h
    src/designgrid.cpp src/designgrid.h
    src/inkitem.cpp src/inkitem.h)
target_link_libraries(centaur_core PUBLIC Qt6::Core Qt6::Gui Qt6::Quick Qt6::Network Qt6::Svg centaur_typography)
target_include_directories(centaur_core PUBLIC src)
target_compile_options(centaur_core PRIVATE -Wall -Wextra -Wpedantic)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_compile_definitions(centaur_core PUBLIC CENTAUR_WAYLAND=1)
endif()
qt_add_resources(centaur_core starter PREFIX "/" FILES templates/App.qml)
file(GLOB DIALOGUE_ASSETS RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}" CONFIGURE_DEPENDS assets/dialogue/*.svg assets/dialogue/*.png)
qt_add_resources(centaur_core dialogue_assets PREFIX "/" FILES ${DIALOGUE_ASSETS})
qt_add_executable(centaur-host src/host_main.cpp)
target_link_libraries(centaur-host PRIVATE centaur_core)
qt_add_executable(centaur src/main.cpp)
target_compile_definitions(centaur PRIVATE CENTAUR_APP_VERSION="${PROJECT_VERSION}+${CENTAUR_BUILD_ID}")
target_link_libraries(centaur PRIVATE centaur_core Qt6::QuickControls2)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_libraries(centaur PRIVATE Qt6::WaylandCompositor)
endif()
qt_add_resources(centaur ui PREFIX "/" FILES
    qml/Main.qml qml/ProjectsView.qml qml/WorkspaceView.qml
    qml/ChatPanel.qml qml/CanvasView.qml qml/FlatButton.qml
    qml/CollaborationDialogs.qml qml/SideNavigation.qml qml/BrandMark.qml qml/DesignSystemsView.qml qml/SettingsView.qml
    qml/Theme.qml qml/qmldir ${PREVIEW_QML})
qt_add_resources(centaur probe PREFIX "/" FILES tests/fixtures/EmbeddedProbe.qml)
qt_add_executable(centaur-preview src/preview_main.cpp)
target_link_libraries(centaur-preview PRIVATE Qt6::Quick Qt6::QuickControls2 centaur_typography)
install(TARGETS centaur centaur-preview centaur-host RUNTIME DESTINATION bin BUNDLE DESTINATION .)
install(FILES assets/fonts/inter/LICENSE.txt DESTINATION share/licenses/centaur/inter)
install(FILES assets/fonts/inter-tight/OFL.txt DESTINATION share/licenses/centaur/inter-tight)
install(FILES assets/dialogue/LICENSE DESTINATION share/licenses/centaur/dialogue)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    install(FILES packaging/centaur.desktop DESTINATION share/applications)
    install(FILES packaging/centaur.svg DESTINATION share/icons/hicolor/scalable/apps)
endif()
if(BUILD_TESTING)
    find_package(Qt6 REQUIRED COMPONENTS Test)
    qt_add_executable(centaur-tests tests/tst_core.cpp)
    target_link_libraries(centaur-tests PRIVATE centaur_core Qt6::Test)
    qt_add_executable(centaur-network-tests tests/tst_network.cpp)
    target_link_libraries(centaur-network-tests PRIVATE centaur_core Qt6::Test)
    if(CENTAUR_NETWORK_EXECUTABLE)
        qt_add_executable(centaur-iroh-tests tests/tst_iroh.cpp)
        target_link_libraries(centaur-iroh-tests PRIVATE centaur_core Qt6::Test)
        add_dependencies(centaur-iroh-tests centaur-network-helper)
        add_test(NAME iroh COMMAND centaur-iroh-tests)
        set_tests_properties(iroh PROPERTIES TIMEOUT 180 ENVIRONMENT "CENTAUR_IROH_LOCAL=1;QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software")
    endif()
    add_test(NAME network COMMAND centaur-network-tests)
    set_tests_properties(network PROPERTIES TIMEOUT 90)
    add_test(NAME core COMMAND centaur-tests)
    set_tests_properties(core PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_test(NAME ui-smoke COMMAND centaur --smoke-test)
    set_tests_properties(ui-smoke PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software")
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        add_test(NAME network-native-embedding COMMAND centaur --network-embedding-smoke-test)
        set_tests_properties(network-native-embedding PROPERTIES TIMEOUT 30 ENVIRONMENT
            "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_WAYLAND_CLIENT_BUFFER_INTEGRATION=shm")
        add_test(NAME native-embedding COMMAND centaur --embedding-smoke-test)
        set_tests_properties(native-embedding PROPERTIES TIMEOUT 25 ENVIRONMENT
            "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_WAYLAND_CLIENT_BUFFER_INTEGRATION=shm")
    endif()
endif()
