/// <reference types="vite/client" />

// `noUncheckedSideEffectImports` is on, so every `import "./x.css"` needs a
// declaration. vite/client supplies the ones for project CSS; @fontsource ships
// bare .css files with no types, so they are declared here.
declare module "@fontsource/*";
declare module "@fontsource-variable/*";
