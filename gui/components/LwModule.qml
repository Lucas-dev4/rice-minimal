import QtQuick

// LwModule.qml — o gancho base: o que um módulo põe na janela fora das telas dele (docs/modulos.md).
// Nenhum campo é obrigatório: todos têm um padrão neutro, e o módulo preenche só o que usa.
// O shell.qml já lê tudo, menos started(), que entra com JOGOS (sessão 5).
Item {
    visible: false

    // ---- o shell.qml preenche; o módulo só lê
    property bool active: false              // a seção deste módulo está aberta
    property int current: 0                  // a tela dele, pela ordem do manifesto
    property bool parked: false              // janela escondida (Ctrl+J)
    property Item keyTarget: null            // quem recebe o foco do teclado depois de um clique

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

    // Pede uma tela da própria seção (só vale com ela aberta).
    signal openScreen(int index)

    // Clique na ponta direita do rodapé.
    function contextClicked() {}
    // A janela abriu.
    function started() {}
    // Entrou na seção.
    function entered() {}
    // Saiu da seção (não é "left": esse nome já é uma âncora do Item).
    function exited() {}
    // A janela está fechando (active: nesta seção).
    function closing(active) {}
    // Uma tela do módulo ficou pronta.
    function screenLoaded(item) {}
    // Teclas: devolvem true quando usaram a tecla.
    function overlayKey(event) { return false; }
    function key(event) { return false; }
    function backgroundKey(event) { return false; }
    // IPC dos testes; act devolve true quando conhece a ação.
    function state() { return ({}); }
    function act(op, arg) { return false; }
}
