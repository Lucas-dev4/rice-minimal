import QtQuick

// LwModule.qml — o gancho base: o que um módulo põe na janela fora das telas dele (docs/modulos.md).
// Todo campo tem um padrão neutro; o módulo preenche só o que usa. O shell.qml já lê sidebar,
// footerLeft, context*, idleText, hints e bootStep; os outros ele passa a ler quando MÚSICA e JOGOS
// saírem de lá (sessões 4 e 5).
Item {
    visible: false

    // ---- barra lateral e tela
    property string summary: ""              // linha da seção fechada
    property Component sidebar: null         // bloco de baixo da barra lateral
    property Component header: null          // cabeçalho comum das telas
    property bool ready: true                // falso: mostra o gate no lugar da tela
    property Component gate: null
    property Component overlay: null         // camada sobre a janela

    // ---- rodapé
    property Component footerLeft: null
    property string context: "—"             // ponta direita
    property bool contextClickable: false
    property string idleText: ""             // mensagem quando nada acontece
    property var hints: []                   // vazio: as dicas comuns da janela
    property var bootStep: null              // { label, done } no boot

    // Clique na ponta direita do rodapé.
    function contextClicked() {}
    // A janela abriu.
    function started() {}
    // Entrou na seção.
    function entered() {}
    // Saiu da seção.
    function left() {}
    // A janela está fechando (active: nesta seção).
    function closing(active) {}
    // Uma tela do módulo ficou pronta.
    function screenLoaded(item) {}
    // Teclas: devolvem true quando usaram a tecla.
    function overlayKey(event) { return false; }
    function key(event) { return false; }
    function backgroundKey(event) { return false; }
    // IPC dos testes.
    function state() { return ({}); }
    function act(op, arg) { return false; }
}
