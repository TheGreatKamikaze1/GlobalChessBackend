export const getGame = async (
 req: Request,
 res: Response,
 next: NextFunction
) => {
 try {
   const gameId = req.params.id;
   const game = await db.game.findUnique({
     where: { id: gameId },
     include: {
       white: { select: { id: true, username: true, displayName: true } },
       black: { select: { id: true, username: true, displayName: true } },
     },
   });
   if (!game) {
     return res.status(404).json({
       success: false,
       error: { code: "GAME_NOT_FOUND", message: "Game not found" },
     });
   }
   return res.json({
     success: true,
     data: {
       id: game.id,
       white: game.white,
       black: game.black,
       stake: game.stake,
       status: game.status,
       moves: JSON.parse(game.moves),
       currentFen: game.currentFen,
       startedAt: game.startedAt,
     },
   });
 } catch (error) {
   next(error);
 }
};
export const makeMove = async (
 req: Request,
 res: Response,
 next: NextFunction
) => {
 try {
   const userId = req.user?.id;
   const gameId = req.params.id;
   const { move } = req.body;
   if (!userId) {
     return res.status(401).json({
       success: false,
       error: { code: "UNAUTHORIZED", message: "Unauthorized" },
     });
   }
   const game = await db.game.findUnique({
     where: { id: gameId },
   });
   if (!game) {
     return res.status(404).json({
       success: false,
       error: { code: "GAME_NOT_FOUND", message: "Game not found" },
     });
   }
   if (game.status !== "ONGOING") {
     return res.status(400).json({
       success: false,
       error: { code: "GAME_ALREADY_ENDED", message: "Game already ended" },
     });
   }
   const moves = JSON.parse(game.moves);
   moves.push(`${move.from}${move.to}`);
   const updatedGame = await db.game.update({
     where: { id: gameId },
     data: { moves: JSON.stringify(moves) },
   });
   return res.json({
     success: true,
     data: {
       gameId,
       move: `${move.from}${move.to}`,
       currentFen: updatedGame.currentFen,
       isCheck: false,
       isCheckmate: false,
       isGameOver: false,
     },
   });
 } catch (error) {
   next(error);
 }
};
export const resignGame = async (
 req: Request,
 res: Response,
 next: NextFunction
) => {
 try {
   const userId = req.user?.id;
   const gameId = req.params.id;
   if (!userId) {
     return res.status(401).json({
       success: false,
       error: { code: "UNAUTHORIZED", message: "Unauthorized" },
     });
   }
   const game = await db.game.findUnique({
     where: { id: gameId },
   });
   if (!game) {
     return res.status(404).json({
       success: false,
       error: { code: "GAME_NOT_FOUND", message: "Game not found" },
     });
   }
   if (game.status !== "ONGOING") {
     return res.status(400).json({
       success: false,
       error: { code: "GAME_ALREADY_ENDED", message: "Game already ended" },
     });
   }
   const winnerId = game.whiteId === userId ? game.blackId : game.whiteId;
   const result = game.whiteId === userId ? "BLACK_WIN" : "WHITE_WIN";
   const updatedGame = await db.game.update({
     where: { id: gameId },
     data: {
       status: "COMPLETED",
       result,
       winnerId,
       completedAt: new Date(),
     },
   });
   // Update user balance
   await db.user.update({
     where: { id: winnerId },
     data: { balance: { increment: game.stake } },
   });
   await db.user.update({
     where: { id: userId },
     data: { balance: { decrement: game.stake } },
   });
   return res.json({
     success: true,
     data: {
       gameId,
       result,
       winnerId,
       message: "You have resigned. Game over.",
     },
   });
 } catch (error) {
   next(error);
 }
};
export const getGameHistory = async (
 req: Request,
 res: Response,
 next: NextFunction
) => {
 try {
   const userId = req.user?.id;
   const limit = Math.min(
     Number.parseInt(req.query.limit as string) || 10,
     100
   );
   const offset = Number.parseInt(req.query.offset as string) || 0;
   if (!userId) {
     return res.status(401).json({
       success: false,
       error: { code: "UNAUTHORIZED", message: "Unauthorized" },
     });
   }
   const games = await db.game.findMany({
     where: {
       OR: [{ whiteId: userId }, { blackId: userId }],
       status: "COMPLETED",
     },
     skip: offset,
     take: limit,
     include: {
       white: { select: { id: true, username: true, displayName: true } },
       black: { select: { id: true, username: true, displayName: true } },
     },
   });
   const total = await db.game.count({
     where: {
       OR: [{ whiteId: userId }, { blackId: userId }],
       status: "COMPLETED",
     },
   });
   return res.json({
     success: true,
     data: games.map((game) => ({
       id: game.id,
       opponent:
         game.whiteId === userId
           ? {
               id: game.blackId,
               username: game.black.username,
               displayName: game.black.displayName,
             }
           : {
               id: game.whiteId,
               username: game.white.username,
               displayName: game.white.displayName,
             },
       stake: game.stake,
       result: game.result,
       moves: JSON.parse(game.moves).length,
       completedAt: game.completedAt,
     })),
     pagination: { total, limit, offset },
   });
 } catch (error) {
   next(error);
 }
};
export const getActiveGames = async (
 req: Request,
 res: Response,
 next: NextFunction
) => {
 try {
   const userId = req.user?.id;
   if (!userId) {
     return res.status(401).json({
       success: false,
       error: { code: "UNAUTHORIZED", message: "Unauthorized" },
     });
   }
   const games = await db.game.findMany({
     where: {
       OR: [{ whiteId: userId }, { blackId: userId }],
       status: "ONGOING",
     },
     include: {
       white: { select: { id: true, username: true, displayName: true } },
       black: { select: { id: true, username: true, displayName: true } },
     },
   });
   return res.json({
     success: true,
     data: games.map((game) => ({
       id: game.id,
       opponent:
         game.whiteId === userId
           ? {
               id: game.blackId,
               username: game.black.username,
               displayName: game.black.displayName,
             }
           : {
               id: game.whiteId,
               username: game.white.username,
               displayName: game.white.displayName,
             },
       stake: game.stake,
       status: game.status,
       startedAt: game.startedAt,
       currentTurn: "white", // TODO: Calculate based on moves
     })),
   });
 } catch (error) {
   next(error);
 }
};