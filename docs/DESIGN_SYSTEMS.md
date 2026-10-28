# Centaur design systems

Design systems should let designers control the quality and consistency of apps generated through conversation. Their architecture must allow different visual languages while preserving app functionality and content.

## Agreed direction

Centaur's interface and generated-app design systems are separate concerns. Retain Qt Quick and make visual implementation independent of platform-default control appearance. Neither Centaur's final identity nor the initial library's visual styles have been selected.

Each independent, versioned system has three layers:

| Layer | Contents |
| --- | --- |
| Tokens | Typography, colours, spacing, radii, borders, shadows, motion and density. |
| Components | Buttons, inputs, checkboxes, navigation, cards, dialogs, lists and menus, including interaction states. |
| Layouts and patterns | Page composition, hierarchy, navigation conventions, responsive behaviour, grouping and component usage rules. |

Themes provide variations within a system, such as light/dark treatments or alternative palettes. Projects record the system and version they use. Agents should use the selected components and patterns from the beginning, and rendered appearance should eventually be evaluated alongside source correctness.

## Current boundary

The prototype accepts and distributes a complete single `App.qml` using built-in modules and bundled fonts. `qml/Theme.qml` styles Centaur's shell; it is not a selectable generated-app design-system library. The Design Systems view is an empty state and import is unavailable.

Reusable modules and multiple files require changes to the agent response, validation, checkpoint, collaboration and packaging contracts. Extracting QML files alone will not deliver system switching.

## Proposed first experiment

Build two or three deliberately different systems as code/configuration before designing a sophisticated editor. Editorial, Utility and Playful are illustrative candidates from the earlier discussion, not chosen product names or final designs:

- **Editorial:** generous spacing, restrained decoration and prominent typography.
- **Utility:** compact controls, denser information and predictable hierarchy.
- **Playful:** expressive colour, larger controls and prominent interaction feedback.

Use one small task app with a list, editable input, action buttons, navigation and a dialog. Generate it with each system, then add content and switch systems on the existing app. Compare hierarchy, spacing, readability, component states and behaviour at the same window sizes. Record whether the agent follows the rules without ad hoc styling.

A proposed shared contract would expose data models, actions, component properties and events independently of presentation. Evaluate whether each system can provide different components and layouts against that contract. Persistent content must survive a switch; treatment of transient state, such as focus, selection or an open dialog, needs an explicit policy. A preview restart may be acceptable for the experiment; seamless live switching has not been agreed as a requirement.

The earlier discussion suggested the following possible organisation. Its folder names and file formats remain illustrative:

```text
MyApp/
  app/
    Main.qml
    pages/
    logic/
  design-system/
    tokens.json
    components/
    patterns/
  project.json
```

Use the experiment to choose what belongs in configuration, QML and composition guidance, and to identify the smallest safe migration from existing apps. A visual library/editor and designer-authored, shareable systems are later proposals informed by that evidence.

## Qt implementation constraints

Qt Quick Controls supports custom visual implementations. Qt recommends customising a cross-platform base style or creating a custom style; native macOS/Windows styles are unsuitable foundations for that customisation. Basic is a candidate, not a selected Centaur design-system format. [Qt 6.8 customisation guidance](https://doc.qt.io/qt-6.8/qtquickcontrols-customize.html)

Qt's global Controls style must be configured before loading QML that imports Controls; it cannot be changed after those types are registered. Therefore, changing that setting is insufficient for switching an already loaded app. Token bindings and replaceable components, or a controlled restart with state restoration, are approaches to evaluate. [Qt 6.8 QQuickStyle](https://doc.qt.io/qt-6.8/qquickstyle.html)

## Open decisions

Choose the schema and version semantics, component contract, layout-rule representation, asset delivery, compatibility checks, state transfer and upgrade/migration behaviour. Define rendered review criteria before claiming consistent design quality. Decide later how designers author, validate and share systems. Track these choices in [Decisions](DECISIONS.md).
