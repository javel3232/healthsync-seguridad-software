import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/js/dist/collapse"; // solo el menú desplegable del navbar en pantallas pequeñas
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";

createApp(App).use(router).mount("#app");
