#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <stdlib.h>
#include <string.h>

#define WINDOW_WIDTH 400
#define WINDOW_HEIGHT 200
#define MAX_TEXT_LENGTH 256

// Fonction pour exécuter la commande
void execute_command(const char* text) {
    char command[512];
    snprintf(command, sizeof(command), "python3 zorya.py -c '%s'", text);
    system(command);
}

// Fonction pour dessiner le texte dans la fenêtre
void render_text(SDL_Renderer *renderer, TTF_Font *font, SDL_Color color, const char *text, int x, int y) {
    SDL_Surface *surface = TTF_RenderText_Solid(font, text, color);
    SDL_Texture *texture = SDL_CreateTextureFromSurface(renderer, surface);
    SDL_Rect rect = {x, y, surface->w, surface->h};
    SDL_RenderCopy(renderer, texture, NULL, &rect);
    SDL_DestroyTexture(texture);
    SDL_FreeSurface(surface);
}

int main(int argc, char *argv[]) {
    SDL_Init(SDL_INIT_VIDEO);
    TTF_Init();

    SDL_Window *window = SDL_CreateWindow("Text Command Interface",
                                          SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                          WINDOW_WIDTH, WINDOW_HEIGHT, SDL_WINDOW_SHOWN);
    SDL_Renderer *renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);

    TTF_Font *font = TTF_OpenFont("arial.ttf", 24);  // Assure-toi d'avoir le fichier font
    SDL_Color textColor = {255, 255, 255};  // Couleur blanche pour le texte
    char inputText[MAX_TEXT_LENGTH] = "";    // Champ de texte
    int textLength = 0;

    SDL_Event event;
    int running = 1;

    while (running) {
        SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);  // Fond noir
        SDL_RenderClear(renderer);

        // Dessiner le champ de texte
        SDL_Rect textBox = {50, 50, 300, 40};
        SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
        SDL_RenderFillRect(renderer, &textBox);

        // Afficher le texte
        render_text(renderer, font, textColor, inputText, 55, 55);

        // Dessiner le bouton "OK"
        SDL_Rect button = {150, 120, 100, 40};
        SDL_SetRenderDrawColor(renderer, 0, 255, 0, 255);
        SDL_RenderFillRect(renderer, &button);
        render_text(renderer, font, textColor, "OK", 170, 130);

        SDL_RenderPresent(renderer);

        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) {
                running = 0;
            }

            // Gestion de la saisie au clavier
            if (event.type == SDL_TEXTINPUT && textLength < MAX_TEXT_LENGTH - 1) {
                strncat(inputText, event.text.text, 1);
                textLength++;
            }

            if (event.type == SDL_KEYDOWN && event.key.keysym.sym == SDLK_BACKSPACE && textLength > 0) {
                inputText[--textLength] = '\0';  // Suppression du dernier caractère
            }

            // Gestion du clic sur le bouton
            if (event.type == SDL_MOUSEBUTTONDOWN) {
                int x = event.button.x, y = event.button.y;
                if (x >= 150 && x <= 250 && y >= 120 && y <= 160) {
                    execute_command(inputText);
                }
            }
        }
    }

    TTF_CloseFont(font);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    TTF_Quit();
    return 0;
}
